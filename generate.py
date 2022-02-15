import glob, os, os.path, re, shutil, tarfile, subprocess, time, sys, random
from urllib.parse import quote
from multiprocessing.pool import ThreadPool

import requests

versions = '-'.join(sys.argv[1:])

target_name = f'perldoc-html-{versions}'
target = os.path.join(os.path.dirname(os.path.realpath(__file__)), target_name)

link_pat = re.compile(br'(<a .*?href=")/(.*?)(#.*?)?(".*?>)')

def get_pages(name):
    r = requests.get(hostname + name, allow_redirects=False)
    if r.status_code != 200:
        return set(), {name: r.headers['Location']} if r.status_code == 301 else {}

    ret = set()
    for mat in link_pat.finditer(r.content):
        ret.add(mat[2].decode())
    return ret, {}


def save(name, name_map, redir_map):
    filename = name_map[name]
    r = requests.get(hostname + name, allow_redirects=False)
    if r.status_code != 200:
        return

    def rep(mat):
        target = redir_map.get(mat[2].decode()) or name_map.get(mat[2].decode())
        return mat[1] + quote(target).encode() + (mat[3] or b'') + mat[4]

    with open(os.path.join(target, filename), 'wb') as fp:
        if filename[-4:] == 'html':
            content = link_pat.sub(rep, r.content)
        else:
            content = r.content
        fp.write(content)


TIMEOUT = 3
CONNECT_RETRY, RETRY_INTERVAL = 20, 0.5
os.makedirs(target, exist_ok=True)
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
    for i in range(CONNECT_RETRY):
        try:
            requests.get(hostname, allow_redirects=False)
            break
        except requests.exceptions.ConnectionError as e:
            err = e
        time.sleep(RETRY_INTERVAL)
    else:
        raise e

    with ThreadPool(4) as pool:
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

        name_map = {}
        for i in names:
            j = str(i)
            if j == '': j = 'index'
            if j[-4:] == 'cpan': j = j[:-4] + '_' + j[-4:]
            if j[-8:] == 'cpan.txt': j = j[:-8] + '_' + j[-8:]
            if os.path.splitext(j)[1] not in ['.txt', '.h', '.pl']: j += '.html'
            name_map[i] = j.replace('::', '__').replace('/', '__').replace('*', '%2A').replace(':', '%3A')
        assert len(name_map) == len(set(name_map.values()))

        for i in sorted(name_map):
            pool.apply_async(save, (i, name_map, redir_map))
        pool.close()
        pool.join()

    realname_pat = re.compile(r'([0-9.]*__)?(.*)')
    with tarfile.open(target + '.tar.gz', 'w:gz') as tar:
        # Sort by real name will put same page of different versions together, thus reducing archive size
        names = sorted(os.listdir(target), key=lambda x: realname_pat.fullmatch(x)[2])
        for i in names:
            tar.add(os.path.join(target, i), arcname=os.path.join(target_name, i))
except KeyboardInterrupt:
    print('Interrupted. Cleaning up...')
finally:
    proc.terminate()
    proc.wait()
    shutil.rmtree(target)
