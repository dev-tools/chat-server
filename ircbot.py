# -*- coding: utf-8 -*-
import sys
import time
from twisted.internet import reactor
from twisted.internet.protocol import ClientFactory
from twisted.words.protocols.irc import IRCClient
from twisted.python import log
from twisted.internet import task

from bash import BashOrg


class IRCBot(IRCClient):
    nickname = "Iriska"

    def dataReceived(self, data):
        log.msg('GET: {0}'.format(data))
        IRCClient.dataReceived(self, data)

    def sendMessage(self, command, *parameter_list, **prefix):
        if not command:
            raise ValueError("IRC message requires a command.")

        if ' ' in command or command[0] == ':':
            raise ValueError("Somebody screwed up, 'cuz this doesn't" \
                  " look like a command to me: %s" % command)

        line = ' '.join([command] + list(parameter_list))
        if 'prefix' in prefix:
            line = ":%s %s" % (prefix['prefix'], line)
        log.msg('SEND: {0}'.format(line))
        self.sendLine(line)

        if len(parameter_list) > 15:
            log.msg("Message has %d parameters (RFC allows 15):\n%s" %
                    (len(parameter_list), line))

    def connectionMade(self):
        IRCClient.connectionMade(self)
        log.msg("[connected at %s]" % time.asctime(time.localtime(time.time())))

    def connectionLost(self, reason):
        IRCClient.connectionLost(self, reason)
        log.msg("[disconnected at %s]" % time.asctime(time.localtime(time.time())))

    # callbacks for events

    def signedOn(self):
        self.join(self.factory.channel)

    def joined(self, channel):
        log.msg("[I have joined {0}]".format(channel))

    def parse_command(self, msg):
        raw = msg.split(' ')
        return raw[0], raw[1:]

    def privmsg(self, user, channel, msg):
        user = user.split('!', 1)[0]
        log.msg("<{0}> {1}".format(user, msg))

        if channel == self.nickname:
            recipient = user
            prefix = ' '

        elif msg.startswith(self.nickname + ":"):
            recipient = channel
            prefix = '{0}: '.format(user)
            msg = msg.replace(self.nickname + ": ", '')

        else:
            return
        command, params = self.parse_command(msg)
        self.botCommand(command, prefix, params, recipient)

    def action(self, user, channel, msg):
        user = user.split('!', 1)[0]
        self.logger.log("* {0} {1}".format(user, msg))

    # irc callbacks

    def irc_NICK(self, prefix, params):
        """Called when an IRC user changes their nickname."""
        old_nick = prefix.split('!')[0]
        new_nick = params[0]
        log.msg("%s is now known as %s" % (old_nick, new_nick))

    def alterCollidedNick(self, nickname):
        """
        Generate an altered version of a nickname that caused a collision in an
        effort to create an unused related name for subsequent registration.
        """
        return nickname + '^'


class BashMixin(object):
    bashloop = False
    bashtimeout = 10

    #TODO
    def joined(self, channel):
        IRCBot.joined(self, channel)
        time.sleep(2)
        loop = task.LoopingCall(self.bash_loop)
        loop.start(self.bashtimeout)

    def startbashloop(self):
        self.taskloop = task.LoopingCall(self.bash_loop)
        self.taskloop.start(self.bashtimeout)

    def stopbashloop(self):
        self.taskloop.stop()

    def bash_loop(self):
        if self.bashloop:
            self.get_bashorg()

    def get_bashorg(self):
        ch = '#' + self.factory.channel
        for s in self.get_bash_quote().split('\n'):
            self.msg(ch, s)
        self.msg(ch, '-' * 150)

    def get_bash_quote(self):
        b = BashOrg()
        return b.get_quote()[0]

    def bot_bash(self, prefix, params, recipient):
        for s in self.get_bash_quote().split('\n'):
            self.msg(recipient, prefix + s)
        self.msg(recipient, prefix + '-' * 150)

    def bot_bashloop(self, prefix, params, recipient):
        bashloop = str(self.bashloop)
        if not len(params):
            self.msg(recipient, prefix + 'Status: {0}'.format(bashloop))
            return
        status = params[0].lower()
        if status not in ['true', 'false']:
            self.msg(recipient, prefix + 'status can be true or false')
            return None
        if status == 'true':
            self.bashloop = bool(1)
        elif status == 'false':
            self.bashloop = bool(0)
        self.msg(recipient, prefix + 'Bashloop set is {0}'.format(status))


class IrcBotCommands(BashMixin, IRCBot):

    def botCommand(self, command, prefix, params, recipient):
        method = getattr(self, "bot_%s" % command, None)
        try:
            if method is not None:
                method(prefix, params, recipient)
            else:
                self.bot_unknown(prefix, command, params, recipient)
        except:
            log.deferr()

    def bot_unknown(self, prefix, command, params, recipient):
        log.msg("{0}, {1}, {2}, {3}, BOT UNKNOWN".format(prefix, command,
                                                         params, recipient))
        self.msg(recipient, prefix + ' UNKNOWN BOT COMMAND')

    def bot_help(self, prefix, params, recipient):
        help_commands = []
        for i in dir(self):
            if i.startswith('bot_') and i != 'bot_unknown' and i != 'bot_help':
                help_commands.append(i.replace('bot_', ''))
        for c in help_commands:
            self.msg(recipient, prefix + c)


class IRCClientFactory(ClientFactory):
    def __init__(self, channel):
        self.channel = channel

    def buildProtocol(self, addr):
        p = IrcBotCommands()
        p.factory = self
        self.p = p
        return p

    def clientConnectionLost(self, connector, reason):
        connector.connect()

    def clientConnectionFailed(self, connector, reason):
        log.msg("connection failed:{0}".format(reason))
        reactor.stop()


if __name__ == "__main__":
    log.startLogging(sys.stdout)
    host = '127.0.0.1'
    port = 6667
    reactor.connectTCP(host, port, IRCClientFactory('dev'))
    reactor.run()