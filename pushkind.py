from daemon import DaemonContext
from time import sleep
from redis import Redis
from pushkin import Pushkin
from json import loads
from threading import Thread, Lock


# FIXME: merge device & commands
def pushkin_send_commands(device, commands):
    with Lock():
        p = Pushkin(**device)
        p.login()
        p.send_commands(commands)
        p.log_output()
        return True


def get_message(bstr):
    if type(bstr) == bytes:
        return bstr.decode()
    return False


def make_courasivo():
    r = Redis()
    p = r.pubsub()
    p.subscribe('ctl')
    while True:
        msg = ''
        m = p.get_message()
        if m and 'data' in m:
            msg = get_message(m['data'])
            if msg == 'stop':
                break
            elif msg == 'new':
                d = r.lpop("device")
                dd = loads(get_message(d))
                t = Thread(target=pushkin_send_commands, args=(dd['device'], dd['commands'],))
                t.start()

        else:
            sleep(.002)


out = open('/home/i/pushkin/daemon.out', 'a+')
err = open('/home/i/pushkin/daemon.err', 'a+')
with DaemonContext(stdout=out, stderr=err):
    make_courasivo()
