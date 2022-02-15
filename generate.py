import glob, os, os.path, re, shutil, tarfile, subprocess, time, sys, random
from urllib.parse import quote
from multiprocessing.pool import ThreadPool

import requests

versions = '-'.join(sys.argv[1:])

target_name = f'perldoc-html-{versions}'
target_dir = os.path.join('..', target_name)
target_archive = os.path.join(os.path.dirname(os.path.realpath(__file__)), target_name + '.tar.xz')

link_pat = re.compile(br'(<(?:a|script|link|img) .*?(?:href|src)=")/(.*?)(#.*?)?(".*?>)')


def get_filename(name):
    j = name
    if j == '': j = 'index'
    if j[-4:] == 'cpan': j = j[:-4] + '_' + j[-4:]
    if j[-8:] == 'cpan.txt': j = j[:-8] + '_' + j[-8:]
    if os.path.splitext(j)[1] not in ['.txt', '.h', '.pl', '.js', '.xml']: j += '.html'
    return j.replace('::', '__').replace('/', '__').replace('*', '%2A').replace(':', '%3A')


def get_pages(name):
    r = requests.get(hostname + name, allow_redirects=False)
    if r.status_code != 200:
        return set(), {name: r.headers['Location']} if r.status_code == 301 else {}

    with open(os.path.join(target_dir, get_filename(name)), 'xb') as fp:
        fp.write(r.content)
    ret = set()
    for mat in link_pat.finditer(r.content):
        ret.add(mat[2].decode())
    return ret, {}


def modify(filename, redir_map):
    def rep(mat):
        target = redir_map.get(mat[2].decode()) or get_filename(mat[2].decode())
        return mat[1] + quote(target).encode() + (mat[3] or b'') + mat[4]

    if filename[-4:] == 'html':
        with open(os.path.join(target_dir, filename), 'rb') as fp:
            content = fp.read()
        content = link_pat.sub(rep, content)
        with open(os.path.join(target_dir, filename), 'wb') as fp:
            fp.write(content)


TIMEOUT = 3
CONNECT_RETRY, RETRY_INTERVAL = 20, 0.5
os.makedirs(target_dir, exist_ok=True)
for i in range(20):
    port = random.randint(3000, 8000)
    hostname = f'http://localhost:{port}/'
    proc = subprocess.Popen(['./perldoc-browser.pl', 'prefork', '-l', hostname],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        if proc.wait(TIMEOUT) != 98:
            print('Unexpected error when starting perldoc-browser.')
            sys.exit(1)
    except subprocess.TimeoutExpired:
        break
else:
    print('Cannot find an available port for perldoc-browser to listen.')
    sys.exit(1)

try:
    try:
        for i in range(CONNECT_RETRY):
            try:
                requests.get(hostname, allow_redirects=False)
                break
            except requests.exceptions.ConnectionError as e:
                err = e
            time.sleep(RETRY_INTERVAL)
        else:
            raise e

        with ThreadPool(5) as pool:
            redir_map = {}
            names = {''}
            prev_names = {''}
            while True:
                result = []
                for i in prev_names:
                    result.append(pool.apply_async(get_pages, (i,)))
                prev_names = set()
                for i in result:
                    nw, redir = i.get()
                    prev_names.update(nw - names)
                    redir_map.update(redir)
                if not prev_names:
                    break
                names |= prev_names
    finally:
        proc.terminate()
        proc.wait()

    for i in os.listdir(target_dir):
        modify(i, redir_map)

    realname_pat = re.compile(r'([0-9.]*__)?(.*)')
    with tarfile.open(target_archive, 'w:xz', preset=5) as tar:
        # Sort by real name will put same page of different versions together, thus reducing archive size
        names = sorted(os.listdir(target_dir), key=lambda x: (realname_pat.fullmatch(x)[2], x))
        for i in names:
            tar.add(os.path.join(target_dir, i), arcname=os.path.join(target_name, i))
except KeyboardInterrupt:
    print('Interrupted. Cleaning up...')
finally:
    shutil.rmtree(target_dir)
