# -*- coding: utf-8 -*-
from twisted.internet.protocol import ServerFactory
from twisted.internet import reactor
from twisted.internet import error
from twisted.words.protocols.irc import IRC
from twisted.words.protocols.irc import symbolic_to_numeric as stn
from twisted.python import log
from twisted.internet import task
from twisted.python import failure
import time
import sys
import socket


connectionDone = failure.Failure(error.ConnectionDone())
connectionDone.cleanFailure()


class IRCServer(IRC):
    hostname = '192.168.0.104'
    auth = False
    version = 'pyirc-0.1'

    def __init__(self, *args, **kwargs):
        self.channels = []
        self.password = ''
        self.username = ''
        self.nickname = ''
        self.mode = ''
        self.unused = ''
        self.realname = ''
        self.timestamp = None

    def __repr__(self):
        return 'USER PROTOCOL:{0}'.format(self.nickname)

    def connectionMade(self):
        log.msg('client connected')
        if self.hostname is None:
            self.hostname = socket.getfqdn()

    def connectionLost(self, reason=connectionDone):
        for ch in self.channels:
            ch.removeuser(self)
        self.factory.user_exit(self)
        IRC.connectionLost(self, reason)

    def get_host(self):
        return self.transport.getPeer().host

    def get_channel(self, name):
        for ch in self.channels:
            if ch.name == name:
                return ch

    def exit_channel(self, name):
        for ch in self.channels:
            if ch.name == name:
                self.channels.remove(ch)
                return None

    def dataReceived(self, data):
        log.msg('GET: {0}'.format(data))
        self.timestamp = time.time()
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
            log.msg("Message has {0} parameters (RFC allows 15):\n{1}".format(len(parameter_list), line))

    def _send_welcome(self):
        self.sendMessage('NOTICE', 'AUTH :*** You connected on 6667 port')
        self.sendMessage(stn['RPL_WELCOME'], self.nickname, ':Welcome to Dev Team IRC')
        self.sendMessage(stn['RPL_YOURHOST'], self.nickname, ':Your host is {0}, running version {1}'.format(self.hostname, self.version))
        self.sendMessage(stn['RPL_CREATED'], self.nickname, ':This server was created Mon Oct 28 2013 at 09:30:23 EEST')
        self.sendMessage(stn['RPL_MYINFO'], self.nickname, self.hostname, self.version, 'iowghraAsORTVSxNCWqBzvdHtGpZI', 'lvhopsmntikrRcaqOALQbSeIKVfMCuzNTGjP') #TODO
        #self.sendMessage(stn['RPL_ISUPPORT'], self.nickname, ':Welcome to Dev Team IRC') #TODO

    def send_PING(self):
        line = 'PING {0} {1}'.format(self.nickname, self.hostname)
        log.msg('SEND: {0}'.format(line))
        self.sendLine(line)

    def irc_unknown(self, prefix, command, params):
        log.msg("{0}, {1}, {2}, IRC UNKNOWN".format(prefix, command, params))

    #Connection command
    def irc_PASS(self, prefix, params):
        """
        <password>
        ERR_NEEDMOREPARAMS +
        ERR_ALREADYREGISTRED -
        """
        if self.password:
            return
        if not len(params):
            self.sendMessage(stn['ERR_NEEDMOREPARAMS'], ':Need more params.')
            return None
        self.password = params[0]

    def irc_NICK(self, prefix, params):
        """
        <nickname>
        ERR_NONICKNAMEGIVEN +
        ERR_ERRONEUSNICKNAME -
        ERR_NICKNAMEINUSE +
        ERR_NICKCOLLISION -
        ERR_UNAVAILRESOURCE +
        ERR_RESTRICTED -
        """
        if not len(params):
            self.sendMessage(stn['ERR_NONICKNAMEGIVEN'], ':No nickname given.')
            return None
        nickname = params[0]
        if len(nickname) > 9:
            #TODO check error???
            self.sendMessage(stn['ERR_UNAVAILRESOURCE'], nickname, ':Max len 9.')
            return None
        if not self.factory.nick_validate(nickname):
            self.sendMessage(stn['ERR_NICKNAMEINUSE'], nickname, ':Nick name in use.')
            return None
        self.nickname = nickname

    def irc_USER(self, prefix, params):
        """
        <user> <mode> <unused> <realname>
        ERR_NEEDMOREPARAMS +
        ERR_ALREADYREGISTRED +
        """
        if len(params) < 4:
            self.sendMessage(stn['ERR_NEEDMOREPARAMS'], self.nickname, ':Need more params.')
            return None
        if not self.factory.username_validate(params[0]):
            self.sendMessage(stn['ERR_ALREADYREGISTRED'], self.nickname, ':Username already registred.')
            return None
        self.username = params[0]
        self.mode = params[1]
        self.unused = params[2]
        self.realname = params[3]
        if not self.auth:
            self._send_welcome()
            self._send_motd()
        #TODO register

    def irc_QUIT(self, prefix, params):
        """
         [ <Quit Message> ]
        """
        self.sendMessage('QUIT', ':Quit: {0}'.format(params[0]), **{'prefix': self.nickname + '!~' + self.username + '@' + self.get_host()})
        log.msg('client is logging off')
        self.transport.loseConnection()
        for ch in self.channels:
            for i in ch.users:
                if i == self:
                    ch.users.remove(i)

    #Working with channels
    def irc_JOIN(self, prefix, params):
        """
        <channel> *(", " <channel>) [ <key> *(", " <key>) ])

        ERR_NEEDMOREPARAMS
        ERR_BANNEDFROMCHAN
        ERR_INVITEONLYCHAN
        ERR_BADCHANNELKEY
        ERR_CHANNELISFULL
        ERR_BADCHANMASK
        ERR_NOSUCHCHANNEL
        ERR_TOOMANYCHANNELS
        ERR_TOOMANYTARGETS
        ERR_UNAVAILRESOURCE
        RPL_TOPIC +
        """
        name = params[0]
        if name[0] != '#':
            name = '#' + name
        ch = self.factory.get_channel(name)
        ch.userjoin(self)
        self.channels.append(ch)
        self.sendMessage('JOIN', ':{0}'.format(ch.name), **{'prefix': self.nickname + '!~' + self.username + '@' + self.get_host()})
        self.sendMessage(stn['RPL_NAMREPLY'], self.nickname, '=', ch.name, ':{0}'.format(' '.join([i.nickname for i in ch.users])))
        self.sendMessage(stn['RPL_ENDOFNAMES'], self.nickname, ch.name, ':{0}'.format('End of /NAMES list.'))
        self.sendMessage(stn['RPL_TOPIC'], self.nickname, ch.name, ':{0}'.format(ch.topic))

    def irc_PART(self, prefix, params):
        """
        <channel> *(", « <channel>) [ <Part Message> ]
        ERR_NEEDMOREPARAMS
        ERR_NOSUCHCHANNEL
        ERR_NOTONCHANNEL
        """
        ch_name = params[0]
        ch = self.factory.get_channel(ch_name)
        ch.removeuser(self)
        self.exit_channel(ch_name)
        self.sendMessage('PART', ch_name, ':{0}'.format('good bye'), **{'prefix': self.nickname + '!~' + self.username + '@' + self.get_host()})

    def irc_LIST(self, prefix, params):
        """
        [ <channel> *(", " <channel>) [ <target> ] ]
        ERR_TOOMANYMATCHES -
        ERR_NOSUCHSERVER -
        RPL_LIST +
        RPL_LISTEND +
        """
        self.sendMessage(stn['RPL_LISTSTART'], self.nickname, 'Channel :Users  Name')
        for ch in self.factory.channel_list:
            self.sendMessage(stn['RPL_LIST'], self.nickname, ch.name, ch.count(), ':[+nt] ' + ch.topic)
        self.sendMessage(stn['RPL_LISTEND'], self.nickname, ':END of /LIST')

    def irc_TOPIC(self, prefix, params):
        """
        <channel> [»: " <topic> ]
        ERR_NEEDMOREPARAMS +
        ERR_NOTONCHANNEL +
        RPL_NOTOPIC +
        RPL_TOPIC +
        ERR_CHANOPRIVSNEEDED -
        ERR_NOCHANMODES -
        """
        if not len(params) or params[0][0] != '#':
            self.sendMessage(stn['ERR_NEEDMOREPARAMS'], self.nickname, ':Need more params.')
            return None
        ch = self.get_channel(params[0])
        if not ch:
            self.sendMessage(stn['ERR_NOTONCHANNEL'], self.nickname, ':Not on channel.')
            return None
        if len(params) == 2:
            ch.topic = params[1]
            for u in ch.users:
                u.sendMessage(stn['RPL_TOPIC'], u.nickname, ch.name, ':{0}'.format(ch.topic))
            return None
        if len(ch.topic):
            self.sendMessage(stn['RPL_TOPIC'], self.nickname, ch.name, ':{0}'.format(ch.topic))
        else:
            self.sendMessage(stn['RPL_NOTOPIC'], self.nickname, ':Not topic.')

    #Sending a message
    def irc_PRIVMSG(self, prefix, params):
        """
        <msgtarget> <text to be sent>
        ERR_NORECIPIENT
        ERR_NOTEXTTOSEND
        ERR_CANNOTSENDTOCHAN
        ERR_NOTOPLEVEL
        ERR_WILDTOPLEVEL
        ERR_TOOMANYTARGETS
        ERR_NOSUCHNICK
        RPL_AWAY
        """
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

    def irc_NOTICE(self, prefix, params):
        """
        <msgtarget> <text>
        """
        pass

    #Working with data users
    def irc_WHO(self, prefix, params):
        """
        [ <mask> [ «o» ] ]
        ERR_NOSUCHSERVER
        RPL_WHOREPLY
        RPL_ENDOFWHO
        """
        ch = self.get_channel(params[0])
        for user in ch.users:
            self.sendMessage(stn['RPL_WHOREPLY'], self.nickname, ch.name, user.nickname)
        self.sendMessage(stn['RPL_ENDOFWHO'], self.nickname, ch.name, ':End of /WHO list.')

    #Working with server
    def _send_motd(self):
        self.sendMessage(stn['RPL_MOTDSTART'], self.nickname,  ':- Message of the Day - ')
        for row in self.factory.MOTD:
            self.sendMessage(stn['RPL_MOTD'], self.nickname,  ':{0}'.format(row))
        self.sendMessage(stn['RPL_ENDOFMOTD'], self.nickname,  ':End of /MOTD command.')

    def irc_MOTD(self, prefix, params):
        """
        [ <target> ]
        RPL_MOTDSTART +
        RPL_MOTD +
        RPL_ENDOFMOTD +
        ERR_NOMOTD +
        """
        if self.factory.MOTD:
            self._sendsend_motd()
            return None
        self.sendMessage(stn['ERR_NOMOTD'], self.nickname,  ':No MOTD.')

    #Other commands
    def irc_PING(self, prefix, params):
        self.sendMessage('PONG')

    def irc_PONG(self, prefix, params):
        pass


class IRCChannel(object):

    def __init__(self, name):
        self.name = name
        self.topic = 'Topic'
        self.users = []

    def count(self):
        return len(self.users)

    def userjoin(self, user):
        if not user in self.users:
            self.users.append(user)
        self.senduserlist()

    def removeuser(self, user):
        for u in self.users:
            if u == user:
                self.users.remove(u)

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
    users = []
    MOTD = ['=' * 150,
            'Добро пожаловать в IRC',
            '',
            'У нас появился чат бот Iriska',
            '',
            'Прошу не обижать :)',
            'что бы узнать список комманд бота отправте ей сообщение help']

    def get_channel(self, name):
        for ch in self.channel_list:
            if ch.name == name:
                return ch
        ch = IRCChannel(name)
        self.channel_list.append(ch)
        return ch

    def user_exit(self, user):
        self.users.remove(user)
        log.msg(self.users)

    def nick_validate(self, nickname):
        for u in self.users:
            if getattr(u, 'nickname').lower() == nickname.lower():
                return False
        return True

    def username_validate(self, username):
        for u in self.users:
            if getattr(u, 'username').lower() == username.lower():
                return False
        return True

    def buildProtocol(self, addr):
        p = IRCServer()
        p.factory = self
        self.users.append(p)
        return p


def closeunactiv(factory):
    for u in factory.users:
        if u.timestamp and (time.time() - u.timestamp) > 90:
            u.transport.loseConnection()


def checkusers(factory):
    log.msg('Online now: {0} | {1}'.format(len(factory.users), factory.users))
    [u.send_PING() for u in factory.users]


if __name__ == "__main__":
    log.startLogging(sys.stdout)
    auth = {'login1': 'password1', 'login': 'password'}

    factory = IRCServerFactory()
    reactor.listenTCP(6667, factory)
    close = task.LoopingCall(closeunactiv, factory)
    close.start(60.0)
    check = task.LoopingCall(checkusers, factory)
    check.start(30.0)
    reactor.run()