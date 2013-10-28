from twisted.internet.protocol import ServerFactory
from twisted.internet import reactor
from twisted.words.protocols.irc import IRC
from twisted.words.protocols.irc import symbolic_to_numeric as stn
from twisted.python import log
import sys
import socket

log.startLogging(sys.stdout)

auth = {'login1': 'password1', 'login': 'password'}


class IRCServer(IRC):
    hostname = '192.168.0.104'
    channels = []
    auth = False
    version = 'pyirc-0.1'

    def connectionMade(self):
        log.msg('client connected')
        if self.hostname is None:
            self.hostname = socket.getfqdn()

    def get_host(self):
        return self.transport.getPeer().host

    def get_channel(self, name):
        for ch in self.channels:
            if ch.name == name:
                return ch

    def dataReceived(self, data):
        log.msg('GET: {0}'.format(data))
        IRC.dataReceived(self, data)

    def sendMessage(self, command, *parameter_list, **prefix):
        if not command:
            raise ValueError("IRC message requires a command.")

        if ' ' in command or command[0] == ':':
            raise ValueError("Somebody screwed up, 'cuz this doesn't look like a command to me: {0}".format(command))

        line = ' '.join([command] + list([str(i) for i in parameter_list]))
        if 'prefix' in prefix:
            line = ":{0} {1}".format(prefix['prefix'], line)
        else:
            line = ':' + self.hostname + ' ' + line
        log.msg('SEND: {0}'.format(line))
        self.sendLine(line)

        if len(parameter_list) > 15:
            log.msg("Message has %d parameters (RFC allows 15):\n{0}".format(len(parameter_list), line))

    #def _authparams(self, *args, **kwargs):
        #for key in kwargs.keys():
            #setattr(self, key, kwargs[key])
        #if getattr(self, 'password', None) and getattr(self, 'username', None):
            #if self.username in auth and auth[self.username] == self.password or True:

                #return None
            ##TODO send ERR_PASSWDMISMATCH
            #self.transport.loseConnection()

    def _send_welcome(self):
        self.sendMessage('NOTICE', 'AUTH :*** You connected on 6667 port')
        self.sendMessage(stn['RPL_WELCOME'], self.nickname, ':Welcome to Dev Team IRC')
        self.sendMessage(stn['RPL_YOURHOST'], self.nickname, ':Your host is {0}, running version {1}'.format(self.hostname, self.version))
        self.sendMessage(stn['RPL_CREATED'], self.nickname, ':This server was created Mon Oct 28 2013 at 09:30:23 EEST')
        self.sendMessage(stn['RPL_MYINFO'], self.nickname, self.hostname, self.version, 'iowghraAsORTVSxNCWqBzvdHtGpZI', 'lvhopsmntikrRcaqOALQbSeIKVfMCuzNTGjP') #TODO
        #self.sendMessage(stn['RPL_ISUPPORT'], self.nickname, ':Welcome to Dev Team IRC') #TODO

    def irc_unknown(self, prefix, command, params):
        log.msg("{0}, {1}, {2}, IRC UNKNOWN".format(prefix, command, params))

    def irc_USER(self, prefix, params):
        if len(params) < 4:
            self.sendMessage(stn['ERR_NEEDMOREPARAMS'], self.nickname, ':Need more params.')
            return None
        #TODO ERR_ALREADYREGISTRED
        self.username=params[0]
        self.mode=params[1]
        self.unused=params[2]
        self.realname=params[3]
        if not self.auth:
            self._send_welcome()

    def irc_NICK(self, prefix, params):
        #TODO ERR_NONICKNAMEGIVEN
        #TODO ERR_ERRONEUSNICKNAME
        #TODO ERR_NICKNAMEINUSE
        #TODO ERR_NICKCOLLISION
        #TODO ERR_UNAVAILRESOURCE
        #TODO ERR_RESTRICTED
        self.nickname = params[0]

    def irc_PASS(self, prefix, params):
        if not len(params):
            self.sendMessage(stn['ERR_NEEDMOREPARAMS'], self.nickname, ':Need more params.')
            return None
        #TODO ERR_ALREADYREGISTRED
        self.password = params[0]

    def irc_PING(self, prefix, params):
        self.sendMessage('PONG')

    def irc_NOTICE(self, prefix, params):
        pass

    def irc_JOIN(self, prefix, params):
        ch = self.factory.get_channel(params[0])
        ch.userjoin(self)
        self.channels.append(ch)
        self.sendMessage('JOIN', ':{0}'.format(ch.name), **{'prefix': self.nickname + '!~' + self.username + '@' + self.get_host()})
        self.sendMessage(stn['RPL_NAMREPLY'], self.nickname, '=', ch.name, ':{0}'.format(' '.join([i.nickname for i in ch.users])))
        self.sendMessage(stn['RPL_ENDOFNAMES'], self.nickname, ch.name, ':{0}'.format('End of /NAMES list.'))
        self.sendMessage(stn['RPL_TOPIC'], self.nickname, ch.name, ':{0}'.format('Welcome to channel'))

    def irc_QUIT(self, prefix, params):
        self.sendMessage('QUIT', ':Quit: {0}'.format(params[0]), **{'prefix': self.nickname + '!~' + self.username + '@' + self.get_host()})
        log.msg('client is logging off')
        self.transport.loseConnection()
        for ch in self.channels:
            for i in ch.users:
                if i == self:
                    ch.users.remove(i)

    def irc_LIST(self, prefix, params):
        self.sendMessage(stn['RPL_LISTSTART'], self.nickname, 'Channel :Users  Name')
        for ch in self.factory.channel_list:
            self.sendMessage(stn['RPL_LIST'], self.nickname, ch.name,
                             ch.count(), ':[+nt] ' + ch.topic)
        self.sendMessage(stn['RPL_LISTEND'], self.nickname, ':END of /LIST')

    def irc_PRIVMSG(self, prefix, params):
        recipient, msg = params[0], params[1]
        if recipient[0] == '#':
            ch = self.get_channel(recipient)
            ch.sendmsg(self, msg)
            return None
        else:
            for ch in self.channels:
                user = ch.getuser(recipient)
                user.sendMessage('PRIVMSG', user.nickname, ':{0}'.format(msg), prefix=self.nickname+'!'+self.username+'@'+self.get_host())
                return None

    def irc_WHO(self, prefix, params):
        ch = self.get_channel(params[0])
        for user in ch.users:
            self.sendMessage(stn['RPL_WHOREPLY'], self.nickname, ch.name, user.nickname)
        self.sendMessage(stn['RPL_ENDOFWHO'], self.nickname, ch.name, ':End of /WHO list.')


class IRCChannel(object):

    def __init__(self, name):
        self.name = name
        self.topic = 'channel topic'
        self.users = []

    def count(self):
        return len(self.users)

    def userjoin(self, user):
        if not user in self.users:
            self.users.append(user)
        self.senduserlist()

    def senduserlist(self):
        users = [i.nickname for i in self.users]
        for user in self.users:
            user.sendMessage(stn['RPL_NAMREPLY'], user.nickname, '=', self.name, ':{0}'.format(' '.join(users)))
            user.sendMessage(stn['RPL_ENDOFNAMES'], user.nickname, self.name, ':{0}'.format('End of /NAMES list.'))

    def sendmsg(self, sender, msg):
        for u in self.users:
            if u != sender:
                u.sendMessage('PRIVMSG', self.name, ':{0}'.format(msg), prefix=sender.nickname+'!'+sender.username+'@'+sender.get_host())

    def getuser(self, nickname):
        for u in self.users:
            if u.nickname.lower() == nickname.lower():
                return u


class IRCServerFactory(ServerFactory):
    channel_list = []

    def get_channel(self, name):
        for ch in self.channel_list:
            if ch.name == name:
                return ch
        ch = IRCChannel(name)
        self.channel_list.append(ch)
        return ch

    def buildProtocol(self, addr):
        p = IRCServer()
        p.factory = self
        return p


factory = IRCServerFactory()
reactor.listenTCP(6667, factory)
reactor.run()