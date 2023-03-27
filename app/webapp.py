from flask import Flask, render_template, request,make_response, redirect, jsonify, abort, g
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from PIL.ExifTags import TAGS
import datetime
import requests
import sys
import os
import io
import numpy
import face_recognition
import base64
from werkzeug.utils import secure_filename
from werkzeug.exceptions import BadRequest, HTTPException, default_exceptions
import sqlite3

py_version = sys.version

APP_HOST = '0.0.0.0'
APP_PORT = '8080'
APP_DEBUG = True

APP_TEMPLATES = r'templates'
APP_STATIC = r'static'
APP_IMGBASE = r'imgbase'

UPLOAD_FOLDER = r'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

DB_PATH = r'db/webapp.db'

thumb_on_page = 15;

app = Flask(__name__, template_folder = APP_TEMPLATES, static_folder = APP_STATIC)

CUR_PATH = os.path.dirname(os.path.realpath(__file__))

def currTime():
        now = datetime.datetime.now()
        return now.strftime("%d.%m.%Y %H:%M:%S")

def getFilesList(searchDir):
        return sorted(os.listdir(searchDir))

def getImagesList(imgPath = ''):
        if (imgPath == ''):
                imgPath = os.path.join(CUR_PATH , APP_IMGBASE)
        allFiles = getFilesList(imgPath)
        imgFiles = []
        for fileitem in allFiles:
                filename, fileext = os.path.splitext(fileitem)
                if (os.path.isfile(os.path.join(imgPath, fileitem)) and (fileext[1:].lower() in ALLOWED_EXTENSIONS)):
                        imgFiles.append(fileitem)
        
        return imgFiles

def get_dbpath():
        dbpath = getattr(g, '_dbpath', None)
        if dbpath is None:
                dbpath = g._dbpath = os.path.join(CUR_PATH , DB_PATH)
        return dbpath

def get_db():
        db = getattr(g, '_database', None)
        if db is None:
                db = g._database = sqlite3.connect(get_dbpath())
                return db
        else:
            return db

def db_query(sqlstr, args=()):
        db = get_db()
        cur = db.cursor()
        cnt = cur.execute(sqlstr, args)
        db.commit()
        rwcnt = cur.rowcount
        cur.close()
        return rwcnt

def db_fetch(sqlstr, args=(), singlrow=False):
        db = get_db()
        cur = db.execute(sqlstr, args)
        rows = cur.fetchall()
        cur.close()
        return (rows[0] if rows else None) if singlrow else rows

def db_init():
        with app.app_context():
                db = get_db()
                with app.open_resource(get_dbpath() + '.sql', mode='r') as f:
                        db.cursor().executescript(f.read())
                db.commit()

db_init()

@app.teardown_appcontext
def close_db_connection(exception):
        db = getattr(g, '_database', None)
        if db is not None:
            db.close()

@app.route("/")
def hello():
        imageslist = getImagesList()
        imagescount = len(imageslist)
        templateData = {
                'apppath' : CUR_PATH,
                'pyversion' : py_version,
                'imageslist' : imageslist,
                'imagescount' : imagescount,
                'staticpath' : APP_STATIC,
        }
        return render_template('index.html', **templateData)

@app.route("/loadfacefider", methods = ['GET', 'POST'])
@app.route('/loadfacefider/<string:imgname>')
def findface(imgname = ""):
        try:
                if (request.method == 'POST'):
                        imgname = request.form['imgname']
                else:
                        imgname = request.args['imgname']
        except:
                pass
        if (imgname == '' or imgname is None):
                abort(404)
        
        faces = find_faces(imgname)
        face_imgs = faces["fimgs"]
        face_count = len(face_imgs)
        
        face_pos = faces["faces"]
        pos_len = len(face_pos)
        
        face_encs = faces["encodings"]
        enc_count = len(face_encs)
        face_encodings = []
        if (enc_count > 0):
                for enc in face_encs:
                        face_encodings.append(", ".join(map(str, enc)))
        
        templateData = {
                'imgname' : imgname,
                'faceimages' : face_imgs,
                'facecount' : face_count,
                'encodings' : face_encodings,
                'enccount' : enc_count,
                'positions' : face_pos,
                'poscount' : pos_len,
                }
        return render_template('facefinder.html', **templateData)

def find_faces(imgname, imgpath=""):
        faces = []
        fimgs = []
        encs = []
        if (imgpath == ""):
                imgPath = os.path.join(CUR_PATH , APP_IMGBASE, imgname)
        imgPath = os.path.join(CUR_PATH, APP_IMGBASE, imgname)
        try:
                img = face_recognition.load_image_file(imgPath)
                face_locations = face_recognition.face_locations(img)
                if len(face_locations) > 0:
                        for face_location in face_locations:
                                top, right, bottom, left = face_location
                                faces.append(face_location)
                                face_image = img[top:bottom, left:right]
                                pil_image = Image.fromarray(face_image)
                                buf = io.BytesIO()
                                pil_image.save(buf, format='PNG')
                                byte_img = buf.getvalue()
                                fimgs.append(base64.b64encode(byte_img).decode())
                
                face_encodings = face_recognition.face_encodings(img)
                if len(face_encodings) > 0:
                        for face_encoding in face_encodings:
                                encs.append(face_encoding)
        except:
            errimg = Image.new('RGB', (200,200), color=('#383030'))
            drawing = ImageDraw.Draw(errimg)
            font = ImageFont.truetype(os.path.join(CUR_PATH , APP_STATIC, 'fonts', 'arial.ttf'), size=18)
            drawing.text((20,80), f"Something wrong with {imgname}", font=font, fill=('#f40808'))
            buf = io.BytesIO()
            errimg.save(buf, format='PNG')
            byte_img = buf.getvalue()
            fimgs.append(base64.b64encode(byte_img).decode())
        return { "faces" : faces, 'fimgs' : fimgs, "encodings" : encs }

@app.route("/loadworkimage", methods = ['GET', 'POST'])
@app.route("/loadworkimage/<string:imgname>", methods = ['GET', 'POST'])
def viewimage(imgname = ''):
        try:
                if (request.method == 'POST'):
                        imgname = request.form['imgname']
                else:
                        imgname = request.args['imgname']
        except:
                pass
        if (imgname == ''  or imgname is None):
                abort(404)
        imgExtData = getImgData(imgname)
        
        imgdata = imgExtData["imgdata"]
        imgcount = len(imgdata)
        
        exifdata = imgExtData["exif"]
        exifcount = len(exifdata)
        
        templateData = {
                'imgname' : imgname,
                'imgdata' : imgdata,
                'imgcount' : imgcount,
                'exifdata' : exifdata,
                'exifcount' : exifcount,
        }
        return render_template('workimage.html', **templateData)

def getImgData(imgname, imgpath=''):
        imgdata = {}
        exif = []
        if (imgpath == ""):
                imgname = os.path.join(CUR_PATH , APP_IMGBASE, imgname)
        try:
                img = Image.open(imgname)
                imgdata["mode"] = img.mode
                imgdata["format"] = img.format
                imgdata["width"] = img.size[0]
                imgdata["heighth"] = img.size[1]
                
                exifdata = img._getexif()
                if len(exifdata) > 0:
                        for tag_id in exifdata:
                                tag = TAGS.get(tag_id, tag_id)
                                data = exifdata.get(tag_id)
                                if isinstance(data, bytes):
                                        try:
                                                data = data.decode()
                                        except Exception as e:
                                                data = e
                                exif.append(f"{tag:25}: {data}")
        except FileNotFoundError as e:
                exif = [f"File {imgname} not found"]
        except OSError as e:
                exif = [f"File {imgname} can`t be open"]
        except Exception as e:
                exif = [e]
        return { "imgdata" : imgdata, "exif" : exif }

@app.route("/image", methods = ['GET', 'POST'])
@app.route("/image/", methods = ['GET', 'POST'])
@app.route("/image/<string:imgname>", methods = ['GET', 'POST'])
def image(imgname='', imgpath=''):
        try:
                if (request.method == 'POST'):
                        imgname = request.form['imgname']
                else:
                        imgname = request.args['imgname']
        except:
                pass
        if (imgname == ''  or imgname is None):
                abort(404)
        if (imgpath == ""):
                imgPath = os.path.join(CUR_PATH , APP_IMGBASE, imgname)
        try:
                if (request.method == 'POST'):
                        mode = request.form['mode']
                else:
                        mode = request.args['mode']
        except:
                mode = 'RGB'
        try:
                if (request.method == 'POST'):
                        imgfilter = request.form['filter']
                else:
                        imgfilter = request.args['filter']
        except:
                imgfilter = ''
                
        mode = mode.upper()
        imgfilter = imgfilter.upper()
        try:
                img = Image.open(imgPath)
                imgFormat = img.format
                imgMode = img.mode
                if (imgMode == 'RGB'):
                        red, green, blue = img.split()
                        zeroed_band = red.point(lambda _: 0)
                        band = (red, green, blue)
                        if (mode == 'R'):
                                band = (red, zeroed_band, zeroed_band)
                        if (mode == 'G'):
                                band = (zeroed_band, green, zeroed_band)
                        if (mode == 'B'):
                                band = (zeroed_band, zeroed_band, blue)
                        img = Image.merge("RGB", band)
                
                if (imgfilter == 'SHARPEN'):
                        img = img.filter(ImageFilter.SHARPEN)
                if (imgfilter == 'BLUR'):
                        img = img.filter(ImageFilter.BLUR)
                if (imgfilter == 'SMOOTH'):
                        img = img.filter(ImageFilter.SMOOTH)
        except Exception as e:
                img = image_stumb(imgname, e)
                imgFormat = 'PNG'
        buf = io.BytesIO()
        img.save(buf, format=imgFormat)
        byte_img = buf.getvalue()
        response = make_response(byte_img)
        response.headers['Content-Type'] = 'image/' + imgFormat.lower()
        return response

def image_stumb(imgname, e = ''):
        img = Image.new('RGB', (600,600), color=('#383030'))
        stumb = ImageDraw.Draw(img)
        font = ImageFont.truetype(os.path.join(CUR_PATH , APP_STATIC, 'fonts', 'arial.ttf'), size=14)
        stumb.text((20,250), f"Something wrong with {imgname} \n {e}", font=font, fill=('#f40808'))
        return img

@app.route("/loadthumbs", methods = ['GET', 'POST'])
@app.route("/loadthumbs/", methods = ['GET', 'POST'])
@app.route('/loadthumbs/<string:spage>')
def thumbs(spage = None):
        try:
                if (request.method == 'POST'):
                        spage = request.form['spage']
                else:
                        spage = request.args['spage']
        except:
                pass
        if (spage is not None):
                page = int(spage) - 1
        else:
                page = 0
        page = 0 if page <= 0 else page
        fileslist = getImagesList()
        imagescount = len(fileslist)

        if imagescount > 0:
                cnt = thumb_on_page
                if (cnt > imagescount):
                        page = 0
                        cnt = imagescount
                if ((page * cnt + cnt) > imagescount):
                        page = imagescount // thumb_on_page
                        start = page * cnt
                        cnt = imagescount - (page * thumb_on_page)
                else:
                        start = page * cnt
                end = start + cnt
                previewlist = fileslist[start:end]
                totalpages = imagescount // thumb_on_page
        else:
                previewlist = []
                start = 0
                end = 0
                totalpages = 0
        previewcount = len(previewlist)
        pages = []
        i = 0
        while i <= totalpages:
                pages.append(i+1)
                i+=1
        templateData = {
                'imagescount' : imagescount,
                'previewlist' : previewlist,
                'previewcount' : previewcount,
                'page' : page + 1,
                'start': start + 1,
                'end' : end,
                'totalpages' : totalpages + 1,
                'cnt' : cnt,
                'pages': pages
        }
        return render_template('thumbs.html', **templateData)

@app.route("/thumb", methods = ['GET', 'POST'])
@app.route("/thumb/", methods = ['GET', 'POST'])
@app.route("/thumb/<string:imgname>")
def thumb(imgname='', imgpath=''):
        try:
                if (request.method == 'POST'):
                        imgname = request.form['imgname']
                else:
                        imgname = request.args['imgname']
        except:
                pass
        if (imgname == ''  or imgname is None):
                abort(404)
        if (imgpath == ""):
                imgPath = os.path.join(CUR_PATH, APP_IMGBASE, imgname)
        try:
            img = Image.open(imgPath)
            imgFormat = img.format
            w, h = img.size
            img.thumbnail((w/4, h/4), Image.ANTIALIAS)
        except Exception as e:
            img = thumb_stumb(imgname, e)
            imgFormat = 'PNG'
        buf = io.BytesIO()
        img.save(buf, format=imgFormat)
        byte_img = buf.getvalue()
        response = make_response(byte_img)
        response.headers['Content-Type'] = 'image/' + imgFormat.lower()
        return response

def thumb_stumb(imgname, e = ''):
        img = Image.new('RGB', (200,200), color=('#383030'))
        stumb = ImageDraw.Draw(img)
        font = ImageFont.truetype(os.path.join(CUR_PATH , APP_STATIC, 'fonts', 'arial.ttf'), size=12)
        stumb.text((10,60), f"Something wrong with {imgname} \n {e}", font=font, fill=('#f40808'))
        return img

@app.route("/saveencoding", methods = ['POST'])
def saveencoding():
        if (request.method == 'POST'):
                try:
                        imgname = request.form['imgname']
                        imgtop = request.form['imgtop']
                        imgright = request.form['imgright']
                        imgbottom = request.form['imgbottom']
                        imgleft = request.form['imgleft']
                        faceenc = request.form['faceenc']
                        fcomment = request.form['comment']
                except:
                        abort(400)
        try:
                rw = db_addface((imgname, imgtop, imgright, imgbottom, imgleft, faceenc, fcomment))
                res = {"result" : rw }
        except sqlite3.Error as e:
                res = { "error" : e }
        response = make_response(jsonify(res))
        response.headers['Content-Type'] = "application/json"
        return response

def db_addface(args):
        sqlstr = """ INSERT INTO faces (
            imgname, 
            imgtop, 
            imgright, 
            imgbottom, 
            imgleft, 
            faceenc, 
            fcomment)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """
        res = db_query(sqlstr, args)
        return res

def  str_to_float_list(s, separator = ', '):
        str_enc_list = s.split(separator)
        if (len(str_enc_list) > 0):
                float_enc_lst = [float(x) for x in str_enc_list]
                return float_enc_lst
                
        return []
        
def list_to_numpy(lst):
        return numpy.array(lst)

@app.route("/compareface", methods = ['POST'])
def compareface():
        face_matches = {}
        if (request.method == 'POST'):
                try:
                        imgname = request.form['imgname']
                        imgtop = request.form['imgtop']
                        imgright = request.form['imgright']
                        imgbottom = request.form['imgbottom']
                        imgleft = request.form['imgleft']
                        faceenc = request.form['faceenc']
                except:
                        abort(400)
                faces = db_fetch("SELECT imgname, faceenc, fcomment FROM faces;")
                known_face_encodings = []
                known_face_imgnames = []
                known_face_comments = []
                face_encoding = list_to_numpy(str_to_float_list(faceenc))
                if (len(faces) != 0):
                       for face in faces:
                                known_face_enc = list_to_numpy(str_to_float_list(face[1]))
                                known_face_encodings.append(known_face_enc)
                                known_face_imgnames.append(face[0])
                                known_face_comments.append(face[2])
                
                matches = face_recognition.compare_faces(known_face_encodings, face_encoding)
                if True in matches:
                        first_match_index = matches.index(True)
                        tmp_match_img = {}
                        tmp_match_img['imgname'] = known_face_imgnames[first_match_index]
                        tmp_match_img['comment'] = known_face_comments[first_match_index]
                        face_matches[tmp_match_img['imgname']] = tmp_match_img
                face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
                best_match_index = numpy.argmin(face_distances)
                if matches[best_match_index]:
                        tmp_match_img = {}
                        tmp_match_img['imgname'] = known_face_imgnames[best_match_index]
                        tmp_match_img['comment'] = known_face_comments[best_match_index]
                        face_matches[tmp_match_img['imgname']] = tmp_match_img
                
                
        #response = make_response(jsonify(face_matches))
        #response.headers['Content-Type'] = "application/json"
        #return response
                
        templateData = {
                'facematches' : face_matches,
                'matchcount' : len(face_matches),
        }
        return render_template('compareface.html', **templateData)



@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(BadRequest)
def handle_bad_request(e):
    return 'bad request!', 400

@app.route("/exit")
def exit():
        sys.exit(0)

if __name__ == "__main__":
    app.run(host=APP_HOST, port=APP_PORT, debug=APP_DEBUG)
