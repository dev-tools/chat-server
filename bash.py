# -*- coding: utf-8 -*-
import urllib2


class BashOrg(object):

    def __init__(self):
        self.webclient = ['Mozilla/5.0 (X11; Linux x86_64)',
                          'AppleWebKit/537.36 (KHTML, like Gecko)',
                          'Ubuntu Chromium/30.0.1599.114',
                          'Chrome/30.0.1599.114 Safari/537.36']
        self.ranklist = {'new': '', 'random': '/random', 'abyss': '/abyss'}
        self.url = 'http://www.bash.im'

    def get_req(self):
        req = urllib2.Request(self.url + self.ranklist[self.rank])
        req.unredirected_hdrs['User-agent'] = ' '.join(self.webclient)
        req.add_header('User-agent', ' '.join(self.webclient))
        return req

    def get_quote(self, rank='random'):
        self.rank = rank
        page = urllib2.urlopen(self.get_req())
        quotes = []
        while True:
            try:
                s = page.next().decode('cp1251').encode('utf8')
                if '<div class="text">' in s:
                    s = s.replace('<div class="text">', '').\
                          replace('</div>', '').\
                          replace('<br />', '\n').\
                          replace('<br>', '\n').\
                          replace('\t', '')
                    quotes.append(s)
            except:
                break

        return quotes
