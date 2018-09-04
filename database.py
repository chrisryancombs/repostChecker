import praw
import config
import sqlite3
import datetime
from datetime import timedelta
from calendar import monthrange
from urllib.request import Request, urlopen
from io import BytesIO
import ssl
from PIL import Image
import dhash
from hashlib import md5
import av

reddit = praw.Reddit(client_id=config.client_id,
                     client_secret=config.client_secret,
                     username=config.username,
                     password=config.password,
                     user_agent=config.user_agent)

context = ssl._create_unverified_context()
user_agent = 'Mozilla/5.0 (iPhone; CPU iPhone OS 5_0 like Mac OS X) AppleWebKit/534.46'

result = []
originalPostDate = []
location = []
finalTimePassed = []
precentageMatched = []


def initDatabase(conn):
    c = conn.cursor()
    c.execute(
        'CREATE TABLE IF NOT EXISTS Posts (Date INT, Content TEXT, Url TEXT, Location TEXT,State INTEGER DEFAULT 1);')
    conn.commit()
    c.close()
    print('Create table.')


def canonical(s):
    return ''.join([c for c in s if not c.isspace()])


def isInt(s):
    try:
        int(s)
        return True
    except:
        return False


def monthDelta(d1, d2):
    delta = 0
    while True:
        mdays = monthrange(d1.year, d1.month)[1]
        d1 += timedelta(days=mdays)
        if d1 <= d2:
            delta += 1
        else:
            break
    return delta


def hashImg(conn, imgUrl, url):
    imgHash = 'invalid'
    try:
        f = BytesIO(urlopen(Request(str(imgUrl), headers={
                    'User-Agent': user_agent}), context=context).read())
    except:
        deleteItem(conn, url)
        print('invalid check so it was ignored')
    else:
        img = Image.open(f)
        imgHash = dhash.dhash_int(img)
    return imgHash


def hashText(txt):
    return md5(txt.encode('utf-8')).hexdigest()


def hashVid(conn, vidUrl, url):
    vidHash = ''
    try:
        container = av.open(vidUrl['reddit_video']['fallback_url'])
    except:
        deleteItem(conn, url)
        print('invalid check so it was ignored')
        vidHash = 'invalid'
    else:
        for frame in container.decode(video=0):
            vidHash += str(dhash.dhash_int(frame.to_image())) + ' '
    return vidHash


def hashGif(conn, gifUrl, url):
    gifHash = ''
    nframes = 0
    try:
        f = BytesIO(urlopen(Request(str(gifUrl), headers={
                    'User-Agent': user_agent}), context=context).read())
        frame = Image.open(f)
    except:
        deleteItem(conn, url)
        print('invalid check so it was ignored')
        gifHash = 'invalid'
    else:
        while frame:
            dhash.dhash_int(frame)
            gifHash += str(dhash.dhash_int(frame)) + ' '
            nframes += 1
            try:
                frame.seek(nframes)
            except EOFError:
                break
    return gifHash


def hashVidDifference(originalHash, newHash):
    cntr = 0
    originalHashList = originalHash.split()
    newHashList = newHash.split()
    frameDifferences = []
    minDifferences = []
    for i in originalHashList:
        for j in newHashList:
            frameDifferences.append(
                dhash.get_num_bits_different(int(i), int(j)))
            cntr += 1
        minDifferences.append(min(frameDifferences))
        frameDifferences = []
    print(sum(minDifferences)/len(minDifferences))
    return sum(minDifferences)/len(minDifferences)


def deleteItem(conn, url):
    c = conn.cursor()
    c.execute('DELETE FROM Posts WHERE Url = ?;', (str(url),))
    conn.commit()
    c.close()
    ignore()


def ignore():
    result[:] = ['delete']
    originalPostDate[:] = [-1]
    location[:] = [-1]
    finalTimePassed[:] = [-1]
    precentageMatched[:] = [-1]


def addToFound(post, precentage):
    result.append(post[0])
    originalPostDate.append(post[1])
    location.append(post[2])
    precentageMatched.append(precentage)

def updateDatabase(conn, url, updateVal):
    c = conn.cursor()
    c.execute('UPDATE Posts SET Location = ? WHERE Url = ?;', (str(updateVal),str(url),))
    conn.commit()
    c.close()

def deleteOldFromDatabase():
    conn = sqlite3.connect('Posts'+config.subSettings[0][0]+'.db')
    c = conn.cursor()
    args = c.execute('SELECT Date, Location FROM Posts;')
    now = datetime.datetime.utcnow()
    for x in args.fetchall():
        if x[1] is not 'top':
            then = datetime.datetime.fromtimestamp(x[0])
            timePassed = (now-then).days
            if timePassed > config.subSettings[0][2] and x[1] is 'new':
                c.execute('DELETE FROM Posts WHERE Date = ?;', (int(x[0]),))
                conn.commit()
                print('deleted an old post')
    c.close()


def isLogged(conn, contentUrl, media, text, url, date, top, hot):
    result[:] = []
    originalPostDate[:] = []
    finalTimePassed[:] = []
    precentageMatched[:] = []
    args = None
    postsToRemove = []
    fiftyTopPosts = []
    cntr = 0
    returnResult = []
    c = conn.cursor()

    now = datetime.datetime.utcnow()
    then = datetime.datetime.fromtimestamp(date)
    timePassed = (now-then).days
    if ((timePassed > config.subSettings[0][2] and not hot) or (timePassed > config.subSettings[0][1] and hot)) and not top:
        ignore()
        print('the post is older than needed')
    else:
        args = c.execute(
            'SELECT COUNT(1) FROM Posts WHERE Url = ?;', (str(url),))
        if list(args.fetchone())[0] != 0:
            if top:
                cntr += 1
                updateDatabase(conn, url, 'top')
                fiftyTopPosts.append(url)
            args = c.execute(
                'SELECT Location FROM Posts WHERE Url = ?;', (str(url),))
            fullResult = list(args.fetchall())
            for i in fullResult:
                if i[0] is 'top' and cntr > 50 and i[0] not in fiftyTopPosts:
                    updateDatabase(conn, url, 'new')
                args = c.execute('SELECT COUNT(*) FROM Posts;')
                rowCount = args.fetchall()[0][0]
                if cntr is rowCount:
                    cntr = 0
                if i[0] is 'hot':
                    if timePassed > config.subSettings[0][1] and timePassed < config.subSettings[0][2]:
                        updateDatabase(conn, url, 'new')
                if i[0] is 'new':
                    if hot:
                        updateDatabase(conn, url, 'hot')

            ignore()
            print('already done')
        else:
            if text != '&#x200B;' and text != '':
                textHash = hashText(text)
                args = c.execute(
                    'SELECT COUNT(1) FROM Posts WHERE Content = ?;', (str(textHash),))
                if list(args.fetchone())[0] != 0:
                    args = c.execute(
                        'SELECT Url, Date, Location FROM Posts WHERE Content = ?;', (str(textHash),))
                    fullResult = list(args.fetchall())
                    for i in fullResult:
                        addToFound(i, 100)
            elif media != None:
                vidHash = hashVid(conn, media, url)
                if isInt(vidHash.replace(' ', '')):
                    args = c.execute(
                        'SELECT COUNT(1) FROM Posts WHERE Content = ?;', (str(vidHash),))
                    if list(args.fetchone())[0] != 0:
                        args = c.execute(
                            'SELECT Url, Date, Location FROM Posts WHERE Content = ?;', (str(vidHash),))
                        fullResult = list(args.fetchall())
                        for i in fullResult:
                            addToFound(i, 100)
                    args = c.execute(
                        'SELECT Url, Date,, Location, Content FROM posts;')
                    for hashed in args.fetchall():
                        if hashed[0] not in result:
                            hashedReadable = hashed[2]
                            if isInt(hashedReadable.replace(' ', '')):
                                hashedDifference = hashVidDifference(
                                    hashedReadable, vidHash)
                                if hashedDifference < config.subSettings[0][2]:
                                    addToFound(
                                        hashed, ((config.subSettings[0][2] - hashedDifference)/config.subSettings[0][2])*100)
            elif contentUrl != '':
                args = c.execute('SELECT COUNT(1) FROM Posts WHERE Content = ?;', (str(
                    contentUrl).replace('&feature=youtu.be', ''),))
                if list(args.fetchone())[0] != 0:
                    args = c.execute('SELECT Url, Date, Location FROM Posts WHERE Content = ?;', (str(
                        contentUrl).replace('&feature=youtu.be', ''),))
                    fullResult = list(args.fetchall())
                    for i in fullResult:
                        addToFound(i, 100)
                if 'gif' in contentUrl and not (contentUrl.endswith('gifv') or 'gifs' in contentUrl):
                    gifHash = hashGif(conn, contentUrl, url)
                    if isInt(gifHash.replace(' ', '')):
                        args = c.execute(
                            'SELECT COUNT(1) FROM Posts WHERE Content = ?;', (str(gifHash),))
                        if list(args.fetchone())[0] != 0:
                            args = c.execute(
                                'SELECT Url, Date, Location FROM Posts WHERE Content = ?;', (str(gifHash),))
                            fullResult = list(args.fetchall())
                            for i in fullResult:
                                addToFound(i, 100)
                        args = c.execute(
                            'SELECT Url, Date,, Location, Content FROM posts;')
                        for hashed in args.fetchall():
                            if hashed[0] not in result:
                                hashedReadable = hashed[2]
                                if isInt(hashedReadable.replace(' ', '')):
                                    hashedDifference = hashVidDifference(
                                        hashedReadable, gifHash)
                                    if hashedDifference < config.subSettings[0][2]:
                                        addToFound(
                                            hashed, ((config.subSettings[0][2] - hashedDifference)/config.subSettings[0][2])*100)
                elif 'png' in contentUrl or 'jpg' in contentUrl:
                    imgHash = hashImg(conn, contentUrl, url)
                    if isInt(imgHash):
                        args = c.execute(
                            'SELECT COUNT(1) FROM Posts WHERE Content = ?;', (str(imgHash),))
                        if list(args.fetchone())[0] != 0:
                            args = c.execute(
                                'SELECT Url, Date, Location FROM Posts WHERE Content = ?;', (str(imgHash),))
                            fullResult = list(args.fetchall())
                            for i in fullResult:
                                addToFound(i, 100)
                        args = c.execute(
                            'SELECT Url, Date, Location Content FROM posts;')
                        for hashed in args.fetchall():
                            if hashed[0] not in result:
                                hashedReadable = hashed[2]
                                if isInt(hashedReadable):
                                    hashedDifference = dhash.get_num_bits_different(
                                        imgHash, int(hashedReadable))
                                    if hashedDifference < config.subSettings[0][2]:
                                        addToFound(
                                            hashed, ((config.subSettings[0][2] - hashedDifference)/config.subSettings[0][2])*100)

    for i in result:
        if i != '' and i != 'delete':
            if reddit.submission(url='https://reddit.com' + i).selftext == '[deleted]':
                c.execute('DELETE FROM Posts WHERE Url = ?;', (str(i),))
                postsToRemove.append(
                    [i, originalPostDate[cntr], precentageMatched[cntr]])
                print('deleted ' + i)
        cntr += 1

    for i in postsToRemove:
        result.remove(i[0])
        originalPostDate.remove(i[1])
        precentageMatched.remove(i[2])

    c.close()
    for i in originalPostDate:
        then = datetime.datetime.fromtimestamp(i)
        timePassed = monthDelta(then, now)
        fullText = (str(timePassed) + ' months ago')
        if timePassed < 1:
            timePassed = (now-then).days
            fullText = (str(timePassed) + ' days ago')
        if timePassed < 1:
            timePassed = (now-then).total_seconds()//3600
            fullText = (str(timePassed) + ' hours ago')
        if timePassed < 1:
            timePassed = (now-then).total_seconds()//60
            fullText = (str(timePassed) + ' minutes ago')
        if timePassed < 1:
            timePassed = (now-then).total_seconds()
            fullText = (str(timePassed) + ' seconds ago')
        finalTimePassed.append(fullText)
    cntr = 0
    for i in result:
        returnResult.append(
            [i, finalTimePassed[cntr], originalPostDate[cntr], location[cntr], precentageMatched[cntr]])
        cntr += 1
    print('Found? {}'.format(returnResult))

    return returnResult


def addPost(conn, date, contentUrl, media, url, text, top, hot):
    c = conn.cursor()
    if text != '&#x200B;' and text != '':
        content = hashText(text)
    else:
        if media != None:
            vidHash = hashVid(conn, media, url)
            if isInt(vidHash.replace(' ', '')):
                content = vidHash
            else:
                content = contentUrl
        elif 'gif' in contentUrl and not (contentUrl.endswith('gifv') or 'gifs' in contentUrl):
            gifHash = hashGif(conn, contentUrl, url)
            if isInt(gifHash.replace(' ', '')):
                content = gifHash
            else:
                content = contentUrl
        elif 'png' in contentUrl or 'jpg' in contentUrl:
            imgHash = hashImg(conn, contentUrl, url)
            if isInt(imgHash):
                content = imgHash
            else:
                content = contentUrl
        else:
            content = contentUrl
    if top:
        locationVar = 'top'
    elif hot:
        locationVar = 'hot'
    else:
        locationVar = 'new'
    c.execute('INSERT INTO Posts (Date, Content, Url, Location) VALUES (?, ?, ?, ?);',
              (int(date), str(content), str(url), str(locationVar),))
    conn.commit()
    c.close()
    print('Added new post - {}'.format(str(url)))
