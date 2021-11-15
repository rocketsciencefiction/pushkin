import logging
from paramiko.client import SSHClient, AutoAddPolicy
from paramiko.sftp_attr import SFTPAttributes
from os.path import expanduser
from socket import socket
from collections import deque
from select import select
from time import sleep
from threading import Thread, Lock

logging.basicConfig(filename="/tmp/pushkin-send-commands.log", level=logging.DEBUG)


class Pushkin:

    def __init__(
            self, ip, port, name, model, username, password,
            enable_password=None, enable_command=None,
        ):
        self.name = name
        self.ip = ip
        self.port = port
        self.username = username
        self.password = password
        self.enable_command = enable_command
        self.enable_password = enable_password
        self.send_command_timeout = .5
        self.output = ''
        self.background_read_thread = None
        self.background_read_thread_lock = Lock()
        self.background_read_timeout = .8
        self.background_read_tick = 30
        self.output_path = "out/"
        self.socket = None

        self.init_socket()
        self.connect_socket()

        if not self.socket:
            raise Exception("Can't establish socket connection {}:{}".format(ip, port))



    def init_socket(self):
        socket = None
        if self.port == 22:
            cl = SSHClient()
            cl.set_missing_host_key_policy(AutoAddPolicy())
            socket = cl
        elif self.port == 23:
            socket = socket()
        self.socket = socket


    def connect_socket(self):
        if self.port == 22:
            self.socket.connect(self.ip, username=self.username, password=self.password)
            self.socket = self.socket.invoke_shell()
        elif self.port == 23:
            self.socket.connect((self.ip, self.port))
            self.send_commands([self.username, self.password])


    def enable(self):
        self.send_commands([self.enable_command, self.enable_password])


    def socket_write_ready(self):
        if self.port == 22:
            return self.socket.send_ready()
        elif self.port == 23:
            r, w, x = select([], [self.socket], [], 0)
            return bool(w)


    def upload_file(self, path_local, path_remote):
        if self.port == 23:
            raise Exception("Method not supported for telnet protocol")
        tr = self.socket.get_transport()
        sftp = tr.open_sftp_client()
        attr = sftp.put(path_local, path_remote)
        if not isinstance(attr, SFTPAttributes):
            raise Exception("Could not upload file to remote ssh host")


    def send_commands(self, commands, newline='\n'):
        if commands:
            commands = deque(commands)
            while commands:
                command = commands.popleft()
                if command:
                    if self.socket_write_ready():
                        self.socket.send(bytes(command + newline, 'ascii'))
                    else:
                        commands.appendleft(command)
                    if self.send_command_timeout:
                        sleep(self.send_command_timeout)
            return True
        return False


    def background_read(self):
        tick = self.background_read_tick
        while tick:
            try:
                r, w, x = select([self.socket], [], [], self.background_read_timeout)
                if r:
                    out = self.socket.recv(1024)
                    with self.background_read_thread_lock:
                        self.output += out.decode('utf8', 'replace')
                    # TODO: try not to sleep
                    sleep(self.background_read_timeout)
                tick -= 1
            except (EOFError, ConnectionResetError, BrokenPipeError):
                return True


    def run_background_read_thread(self):
        t = Thread(target=self.background_read)
        name = t.getName()
        t.setName("{} [{}]".format(name, self.ip))
        t.start()
        self.background_read_thread = t


    def get_output(self):
        with self.background_read_thread_lock:
            out = self.output
            self.output = ''
        return out


    def start_outputting(self):
        self.run_background_read_thread()
        while self.background_read_thread.is_alive():
            with open("{}/{}".format(self.output_path, self.ip), 'a+') as f:
                output = self.get_output()
                if output:
                    f.write(output)
            sleep(self.background_read_timeout)




