# -*- coding: utf-8 -*-
import sys
import time
from twisted.internet import reactor
from twisted.internet.protocol import ClientFactory
from twisted.words.protocols.irc import IRCClient
from twisted.python import log
from twisted.internet import task

from bash import BashOrg


log.startLogging(sys.stdout)
host = '127.0.0.1'
port = 6667


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
        time.sleep(3)
        self.bash_start()
        log.msg("[I have joined {0}]".format(channel))

    def privmsg(self, user, channel, msg):
        user = user.split('!', 1)[0]
        log.msg("<{0}> {1}".format(user, msg))

        if channel == self.nickname:
            msg = "It isn't nice to whisper!  Play nice with the group."
            self.msg(user, msg)
            return

        if msg.startswith(self.nickname + ":"):
            msg = "{0}: I am a twisted bot".format(user)
            self.msg(channel, msg)
            log.msg("<{0}> {1}".format(self.nickname, msg))

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

    def bash_start(self):
        bashloop = task.LoopingCall(self.get_bashorg)
        bashloop.start(10.0)

    def get_bashorg(self):
        ch = '#' + factory.channel
        b = BashOrg()
        msg = b.get_quote()[0]
        for s in msg.split('\n'):
            self.msg(ch, s)
        self.msg(ch, '-' * 150)



class IRCClientFactory(ClientFactory):
    def __init__(self, channel):
        self.channel = channel

    def buildProtocol(self, addr):
        p = IRCBot()
        p.factory = self
        self.p = p
        return p

    def clientConnectionLost(self, connector, reason):
        connector.connect()

    def clientConnectionFailed(self, connector, reason):
        log.msg("connection failed:{0}".format(reason))
        reactor.stop()


factory = IRCClientFactory('dev')
reactor.connectTCP(host, port, factory)
#bashloop = task.LoopingCall(get_bashorg, factory)
#bashloop.start(10.0)
reactor.run()