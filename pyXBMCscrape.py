#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""An nfo scraper and art fetcher for XBMC
"""

__author__ = "Richard Peng"
__version__ = "0.1"

import sys
import re
import os
import codecs
import urllib
from optparse import OptionParser
import difflib

import imdb
import tmdb
from lxml import etree

TAGS = '(?:(\d{3,4})[i|p]|hd.*dvd|blu.*ray|dvd|unrated|extended|ac3|hdtv|dir.*?cut|patched|b[d|r]rip|limited|[\[\(]).*'

class XbmcXML:
    def __init__(self, filename, options):
        self.title = ""
        self.root = etree.Element("movie")
        self.filename = filename
        self.nfopath = os.path.splitext(self.filename)[0] + ".nfo"
        if os.path.exists(self.nfopath) and not options.rescrape:
            print "NFO exists:", self.nfopath
        else:
            self.rawmovie = None
            if options.imdbid:
                print options.imdbid
                self.getIMDB(options.imdbid)
            else:
                self.searchIMDB(self.filename)
    
    def parseIMDB(self, movie):
        print "Scraping:", self.title
        self.append("title", self.title)
        self.append("originaltitle", self.getIMDBtag(movie, 'title'))
        self.append("sorttitle", self.title)
        self.append("set", "")
        self.append("rating", self.getIMDBtag(movie, 'rating'))
        self.append("year", self.getIMDBtag(movie, 'year'))
        self.append("top250", self.getIMDBtag(movie, 'top 250 rank'))
        self.append("votes", self.getIMDBtag(movie, 'votes'))
        self.append("outline", self.getIMDBtag(movie, 'plot outline'))
        self.append("plot", self.getIMDBtag(movie, 'plot'))
        self.append("taglines", self.getIMDBtag(movie, 'taglines'))
        self.append("runtime", self.getIMDBtag(movie, 'runtimes'))
        self.append("thumb", self.getIMDBtag(movie, 'cover url'))
        self.append("mpaa", self.getIMDBtag(movie, 'mpaa'))
        self.append("studio", self.getIMDBtag(movie, 'production companies'))
        self.append("playcount", "0")
        self.append("watched", "false")
        self.append("id", "tt"+movie.movieID)
        self.extend("genre", self.getIMDBtag(movie, 'genres'))
        #trailer
        self.append("credits", self.getIMDBtag(movie, 'writer'))
        self.append("director", self.getIMDBtag(movie, 'director'))
        self.getIMDBactors(movie, 'cast')
        
    def getIMDBtag(self, movie, key):
        if key in movie.keys():
            if key == 'runtimes':
                return movie[key][0] + " min"
            elif key == 'plot':
                return unicode(re.sub(re.compile("::.*", re.DOTALL),"",movie[key][0]))
            elif key == 'plot outline':
                return unicode(re.sub(re.compile(u'».*', re.DOTALL),"",movie[key])).strip()
            elif key in ['writer', 'director', 'taglines', 'production companies']:
                return unicode(movie[key][0])
            elif key in ['rating', 'year', 'votes', 'top 250 rank']:
                return str(movie[key])
            elif key == 'genres':
                return movie[key]
            else:
                return unicode(movie[key])
        else:
            if key == 'top 250 rank':
                return "0"
            else:
                return ""
    
    def getIMDBactors(self, movie, key):
        if key in movie.keys():
            for person in movie[key]:
                actor = etree.SubElement(self.root, "actor")
                etree.SubElement(actor, "name").text = unicode(person)
                etree.SubElement(actor, "role").text = unicode(person.currentRole)
    
    def searchIMDB(self, filename):
        moviename = get_moviename(filename)
        i = imdb.IMDb()
        search = i.search_movie(moviename)
        if len(search) == 0:
            print "Movie not found:", moviename
        else:
            search = search[0]
            movieID = search.movieID
            oldID = None
            if mismatch(moviename, search['title']):
                print "Possible mismatch for: %s\n" % moviename
                print "Search Result"
                print "============="
                print "Title: %s (%s)" % (search['title'], search['year'])
                print i.get_imdbURL(search)
                oldID = movieID
                movieID = prompt_mm("imdb", oldID)
            if movieID == "-1":
                print "Skipping NFO scrape"
            else:
                self.rawmovie = self.getmovie(movieID)
                self.title = self.rawmovie['title']
                if movieID == oldID:
                    titles = [self.title]
                    for name in self.rawmovie['akas']:
                        if len(name.split(" - ")) == 2:
                            titles.append(name.split(" - ")[0][1:-1])
                    titles = sorted(set(titles))
                    for cand in titles:
                        print titles.index(cand), cand
                    self.title = titles[prompt_sel(titles, "movie name")]
                self.parseIMDB(self.rawmovie)

    def getmovie(self, movieID):
        i = imdb.IMDb()
        movie = i.get_movie(movieID)
        i.update(movie, 'taglines')
        return movie

    def getIMDB(self, movieID):
        self.rawmovie = self.getmovie(movieID)
        self.title = self.rawmovie['title']
        self.parseIMDB(self.rawmovie)
    
    def append(self, tag, value):
        etree.SubElement(self.root, tag).text = value
    
    def extend(self, tag, values):
        for value in values:
            etree.SubElement(self.root, tag).text = unicode(value)
    
    def tostring(self):
        return etree.tostring(self.root, pretty_print=True, encoding=unicode)
        
    def write(self):
        with codecs.open(self.nfopath, 'w', 'utf-8') as nfo:
            nfo.write(self.tostring())

def get_moviename(filename):
    # remove file extension
    name = os.path.splitext(os.path.basename(filename))[0]
    # remove periods and underscores
    name = re.sub('[\._]',' ',name)
    # list of common tags in filenames
    reg = re.compile(TAGS, re.IGNORECASE)
    # remove common tags
    name = re.sub(reg,'',name).strip()
    # remove the year
    name = re.sub('\d{4}$','',name).strip()
    # return the cleaned-up movie name
    return name

def mismatch(orig, search):
    if len(difflib.get_close_matches(orig, [search])) == 0:
        return True
    else:
        regex = re.compile('(I+|\d+)$')
        sequel = re.search(regex, orig)
        search_sequel = re.search(regex, search)
        if not sequel and not search_sequel:
            return False
        else:
            if sequel and search_sequel:
                if sequel.group(0) == search_sequel.group(0):
                    return False
                else:
                    return True
            else:
                return True
                
def prompt_sel(sellist, seltype):
    num = len(sellist) - 1
    while True:
        sel = raw_input("Pick a " + seltype + " [0]: ")
        try:
            if sel == "":
                return 0
            elif int(sel) > num or int(sel) < 0:
                raise IndexError
            else:
                return int(sel)
        except (IndexError, ValueError):
            print "Enter a value from 0-" + str(num)
        
def prompt_mm(db, movieID):
    while True:
        prompt = "Input the correct %s ID [%s]: " % (db, movieID)
        newID = raw_input(prompt)
        if newID == "" and movieID:
            return movieID
        elif newID == "-1":
            return newID
        elif db == "imdb" and re.match('\d{7}',newID):
            return newID
        elif db == "tmdb" and re.match('\d+',newID):
            return newID

class tmdbArt:
    def __init__(self, filename, options):
        moviename = get_moviename(filename)
        if options.tmdbid:
            dbid = options.tmdbid
        else:
            results = tmdb.search(get_moviename(filename))
            if len(results) == 0:
                print "Movie not found in TMDB:", moviename
                dbid = prompt_mm("tmdb", "")
            else:
                search = results[0]
                dbid = search['id']
                if mismatch(moviename, search['name']):
                    print "Possible mismatch for: %s\n" % moviename
                    print "Search Result"
                    print "============="
                    print "Title: %s (%s)" % (search['name'], search['released'])
                    print search['url']
                    dbid = prompt_mm("tmdb", search['id'])
        if dbid == "-1":
            print "Skipping art fetch"
        else:
            self.rawmovie = tmdb.getMovieInfo(dbid)
            print "Retrieving art:", self.rawmovie['name']

            posterurl = self.get_url(self.rawmovie, "poster", options.interactive)
            if posterurl:
                posterpath = self.get_artpath(filename, posterurl, "poster")
                if not options.rescrape and os.path.exists(posterpath):
                    print "Art already exists:", posterpath
                else:
                    self.save_art(posterurl,posterpath)
            else:
                print "No posters found"

            backdropurl = self.get_url(self.rawmovie, "backdrop", options.interactive)
            if backdropurl:
                backdroppath = self.get_artpath(filename, backdropurl, "backdrop")
                if not options.rescrape and os.path.exists(backdroppath):
                    print "Art already exists:", backdroppath
                else:
                    self.save_art(backdropurl, backdroppath)
            else:
                print "No backdrops found"

    def get_url(self, movie, arttype, interactive):
        if arttype == "poster":
            images = movie['images'].posters
        elif arttype == "backdrop":
            images = movie['images'].backdrops
        if len(images) == 0:
            return None
        if interactive:
            for image in images:
                print images.index(image), image['original']
            sel = prompt_sel(images, arttype)
        else:
            sel = 0
        return images[sel]['original']
    
    def get_artpath(self, filename, url, arttype):
        folder = os.path.dirname(filename)
        shortname = os.path.splitext(os.path.basename(filename))[0]
        ext = os.path.splitext(url)[1]
        if arttype == "backdrop":
            return os.path.join(folder,"%s-fanart%s") % (shortname, ext)
        elif arttype == "poster":
            return os.path.join(folder,"%s.tbn") % shortname

    def save_art(self, url,dest):
        print dest
        urllib.urlretrieve(url,dest)

if __name__ == '__main__':
    usage = "usage: %prog [options] filenames"
    parser = OptionParser(usage=usage)
    parser.add_option("-i", action="store_true", dest="interactive", default=False,
                        help="Interactively choose poster and backdrop")
    parser.add_option("-r", action="store_true", dest="rescrape", default=False,
                        help="Rescrape files and images")
    parser.add_option("--no-nfo", action="store_true", dest="no_imdb", default=False,
                        help="Do not fetch or create nfo")
    parser.add_option("--no-art", action="store_true", dest="no_tmdb", default=False,
                        help="Do not fetch art")
    parser.add_option("--imdb", dest="imdbid",
                        help="Specify the IMDB ID to scrape")
    parser.add_option("--tmdb", dest="tmdbid",
                        help="Specify the TMDB ID to fetch art")
    (options, args) = parser.parse_args()
    
    for filename in args:
        fileext = os.path.splitext(filename)[1]
        if fileext in ['.mkv', '.avi', '.mp4']:
            if os.path.exists(filename):
                if not options.no_imdb:
                    #IMDB
                    xbmc = XbmcXML(filename, options)
                    xbmc.write()

                if not options.no_tmdb:
                    #TMDB
                    art = tmdbArt(filename, options)
            else:
                print "File not found: %s" % filename
        else:
            print "Not a movie file:", filename
