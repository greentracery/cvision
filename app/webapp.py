"""
        CVision - Experimental training web application using dlib/face_recognition & Flask.
        Allows you to load images, find faces in images and save them for later comparison and search, 
        compare faces in photos with previously saved ones and search for similar faces in photos, 
        calculate the percentage of matches and the distance between faces found and previously saved.
        It also allows you to change loaded images (8-bit grayscale - RGB - CMYK), 
        use filters by color channels (R,G,B or C,M,Y,K), use blur, sharpen, smooth or counter filtres.
"""
from flask import Flask, render_template, request,make_response, redirect, jsonify, abort, g
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from PIL.ExifTags import TAGS
import datetime
import requests
import sys
import os
import io
import math
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

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

DB_PATH = r'db/webapp.db'

thumb_on_page = 15;

app = Flask(__name__, template_folder = APP_TEMPLATES, static_folder = APP_STATIC)

CUR_PATH = os.path.dirname(os.path.realpath(__file__))

def currTime():
        now = datetime.datetime.now()
        return now.strftime("%d.%m.%Y %H:%M:%S")

def getFilesList(searchDir):
        """ Return list of all files in selected folder """
        return sorted(os.listdir(searchDir))

def getImagesList(imgPath = ''):
        """ Return list of image files in selected folder """
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
        rwcnt = 0
        try:
                cnt = cur.execute(sqlstr, args)
                db.commit()
                rwcnt = cur.rowcount
        finally:
                cur.close()
        return rwcnt

def db_fetch(sqlstr, args=(), singlrow=False):
        db = get_db()
        rows = []
        try:
                cur = db.execute(sqlstr, args)
                rows = cur.fetchall()
        finally:
                cur.close()
        return (rows[0] if rows else []) if singlrow else rows

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
        """ Default route, render 'index.html' template """
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
        
@app.route("/imglist/update", methods = ['GET', 'POST'])
def imglist_update():
        """ Update list of images in header, render 'imglist_options.html' template """
        imageslist = getImagesList()
        imagescount = len(imageslist)
        templateData = {
                'imageslist' : imageslist,
                'imagescount' : imagescount,
        }
        return render_template('imglist_options.html', **templateData)

@app.route("/upload", methods = ['POST'])
def uploadimage():
        """ Upload new image """
        try:
                if request.method != 'POST':
                        raise Exception("Unsupported method")
                if 'file' not in request.files:
                        raise Exception("No file(s) was uploaded")
                file = request.files['file']
                if file.filename == '':
                        raise Exception("No file(s) was selected")
                if file and allowed_file(file.filename):
                        filename = secure_filename(file.filename)
                        file.save(os.path.join(CUR_PATH , APP_IMGBASE, filename))
                        res = {"result" : filename }
                else:
                        raise Exception(f"Cannot upload file {filename}")
        except FileNotFoundError:
                res = { "error" : f"File {filename} is unalavaible" }
        except OSError as e:
                res = { "error" : str(e) }
        except SystemError as e:
                res = { "error" : str(e) }
        except Exception as e:
                res = { "error" : str(e) }
        response = make_response(jsonify(res))
        response.headers['Content-Type'] = "application/json"
        return response
        
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/loadfacefider", methods = ['GET', 'POST'])
@app.route('/loadfacefider/<string:imgname>')
def findface(imgname = ""):
        """ Render 'facefinder.html' template with founded faces """
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
        img_src = faces["img"]
        img_data = faces["imgdata"]
        
        templateData = {
                'imgname' : imgname,
                'faceimages' : face_imgs,
                'facecount' : face_count,
                'encodings' : face_encodings,
                'enccount' : enc_count,
                'positions' : face_pos,
                'poscount' : pos_len,
                'imgsrc' : img_src,
                'imgdata' : img_data,
                }
        return render_template('facefinder.html', **templateData)

def find_faces(imgname):
        """ Try to find faces on image, return list of founded faces with images (in base64) """
        faces = []
        fimgs = []
        encs = []
        out_img = None
        modes = get_image_modes()
        try:
                imgPath = os.path.join(CUR_PATH, APP_IMGBASE, imgname)
                #img = face_recognition.load_image_file(imgPath) # returns numpy array
                filename, fileext = os.path.splitext(imgname)
                if not os.path.isfile(imgPath) or (fileext[1:].lower() not in ALLOWED_EXTENSIONS):
                        raise Exception(f"Source file {imgname} is unavalaible")
                image = Image.open(imgPath)
                imgdata = {}
                imgdata["mode"] = image.mode
                imgdata["format"] = image.format
                imgdata["width"] = image.size[0]
                imgdata["heighth"] = image.size[1]
                """ Image must be 8-bit grayscale or RGB, others types are unsupported - so, convert to RGB """
                if imgdata["mode"] != 'RGB':
                        image, f, m = convert_image_mode(image)
                img = to_numpy_array(image)
                face_locations = face_recognition.face_locations(img)
                if len(face_locations) > 0:
                        for face_location in face_locations:
                                top, right, bottom, left = face_location
                                faces.append(face_location)
                                face_image = img[top:bottom, left:right]
                                pil_image = Image.fromarray(face_image)
                                buf = io.BytesIO()
                                pil_image.save(buf, format='PNG')
                                img_bytes = buf.getvalue()
                                fimgs.append(base64.b64encode(img_bytes).decode())
                                """ draw face frames on source image: """
                                draw = ImageDraw.Draw(image)
                                draw.rectangle((left, top, right, bottom), fill=None, outline=(0, 250, 0), width=3)
                """ save copy of source image with frames on faces: """
                buf = io.BytesIO()
                image.save(buf, format='JPEG', quality=80)
                image_bytes = buf.getvalue()
                out_img = base64.b64encode(image_bytes).decode()
                
                face_encodings = face_recognition.face_encodings(img)
                if len(face_encodings) > 0:
                        for face_encoding in face_encodings:
                                encs.append(face_encoding)
        except Exception as e:
                errimg = image_stumb(imgname, e)
                imgdata = {}
                imgdata["mode"] = errimg.mode
                imgdata["format"] = errimg.format
                imgdata["width"] = errimg.size[0]
                imgdata["heighth"] = errimg.size[1]
                buf = io.BytesIO()
                errimg.save(buf, format='PNG')
                byte_img = buf.getvalue()
                out_img = base64.b64encode(byte_img).decode()
        return { 
                "faces" : faces, 
                'fimgs' : fimgs, 
                "encodings" : encs, 
                'img': out_img, 
                'imgdata': {
                        'mode': f"{imgdata['mode']} ({modes[imgdata['mode']]})",
                        'format': imgdata["format"],
                        'width': imgdata["width"],
                        'height': imgdata["heighth"],
                },
        }

@app.route("/loadworkimage", methods = ['GET', 'POST'])
@app.route("/loadworkimage/<string:imgname>", methods = ['GET', 'POST'])
def viewimage(imgname = ''):
        """ Render 'workimage.html' template contains current image with image information """
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
        
        imgmodes = get_image_modes()
        
        templateData = {
                'imgname' : imgname,
                'imgdata' : imgdata,
                'imgcount' : imgcount,
                'exifdata' : exifdata,
                'exifcount' : exifcount,
                'imgmodes': imgmodes,
        }
        return render_template('workimage.html', **templateData)

def getImgData(imgname):
        """ Return information about image & EXIF-data """
        imgdata = {}
        exif = []
        try:
                imgPath = os.path.join(CUR_PATH , APP_IMGBASE, imgname)
                img = Image.open(imgPath)
                imgdata["mode"] = img.mode
                imgdata["format"] = img.format
                imgdata["width"] = img.size[0]
                imgdata["heighth"] = img.size[1]
                
                exifdata = img._getexif()
                if exifdata is not None and len(exifdata) > 0:
                        for tag_id in exifdata:
                                tag = TAGS.get(tag_id, tag_id)
                                data = exifdata.get(tag_id)
                                if isinstance(data, bytes):
                                        try:
                                                data = data.decode()
                                        except Exception as e:
                                                data = str(e)
                                exif.append(f"{tag:25}: {data}")
        except FileNotFoundError as e:
                exif = [f"File {imgname} is unavalaible"]
        except OSError as e:
                exif = [f"File {imgname} can`t be open"]
        except Exception as e:
                exif = [e]
        return { "imgdata" : imgdata, "exif" : exif }

@app.route("/image", methods = ['GET', 'POST'])
@app.route("/image/", methods = ['GET', 'POST'])
@app.route("/image/<string:imgname>", methods = ['GET', 'POST'])
def image(imgname=''):
        """ Return image file or stumb """
        try:
                if (request.method == 'POST'):
                        imgname = request.form['imgname']
                else:
                        imgname = request.args['imgname']
        except:
                pass
        if (imgname == ''  or imgname is None):
                abort(404)
        
        """ Get request params: """
        try:
                if (request.method == 'POST'):
                        colorfilter = validate(request.form['color'])
                else:
                        colorfilter = validate(request.args['color'])
        except:
                colorfilter = None
        try:
                if (request.method == 'POST'):
                        imgfilter = validate(request.form['filter'])
                else:
                        imgfilter = validate(request.args['filter'])
        except:
                imgfilter = None
        try:
                if (request.method == 'POST'):
                        imgconvert = validate(request.form['convert'])
                else:
                        imgconvert = validate(request.args['convert'])
        except:
                imgconvert = None
        try:
                imgPath = os.path.join(CUR_PATH , APP_IMGBASE, imgname)
                filename, fileext = os.path.splitext(imgname)
                if not os.path.isfile(imgPath) or (fileext[1:].lower() not in ALLOWED_EXTENSIONS):
                        raise Exception(f"Source file {imgname} is unavalaible")
                img = Image.open(imgPath)
                imgFormat = img.format
                imgMode = img.mode
                """ mode convertation: """
                if imgconvert is not None:
                        img, imgFormat, imgMode = convert_image_mode(img, imgconvert)
                """ color filter """
                if colorfilter is not None:
                        img = apply_color_filter(img, colorfilter)
                """ blur/sharpen filter: """
                if imgfilter is not None:
                        img = apply_image_filter(img, imgfilter)
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
        """ Generate stumb image """
        img = Image.new('RGB', (600,600), color=('#383030'))
        stumb = ImageDraw.Draw(img)
        e = str(e)
        font = ImageFont.truetype(os.path.join(CUR_PATH , APP_STATIC, 'fonts', 'arial.ttf'), size=15)
        stumb.text((20,250), f"Something wrong with {imgname} \n {e}", font=font, fill=('#f40808'))
        return img
        
def convert_image_mode(img, mode='RGB'):
        imgformat = img.format
        imgmode = img.mode
        modes = get_image_modes()
        if mode in modes:
                img = img.convert(mode)
        if mode in ('P', 'RGBA'):
                imgformat = 'PNG'
        imgmode = mode
        return img, imgformat, imgmode
        
def apply_image_filter(img, imgfilter):
        if (imgfilter == 'SHARPEN'):
                img = img.filter(ImageFilter.SHARPEN)
        if (imgfilter == 'BLUR'):
                img = img.filter(ImageFilter.BLUR)
        if (imgfilter == 'SMOOTH'):
                img = img.filter(ImageFilter.SMOOTH)
        if (imgfilter == 'CONTOUR'):
                img = img.filter(ImageFilter.CONTOUR)
        return img

def apply_color_filter(img, colorfilter):
        imgmode = img.mode
        if (imgmode == 'RGB'):
                red, green, blue = img.split()
                zeroed_band = red.point(lambda _: 0)
                band = (red, green, blue)
                if (colorfilter == 'R'):
                        band = (red, zeroed_band, zeroed_band)
                if (colorfilter == 'G'):
                        band = (zeroed_band, green, zeroed_band)
                if (colorfilter == 'B'):
                        band = (zeroed_band, zeroed_band, blue)
                img = Image.merge("RGB", band)
        if (imgmode == 'CMYK'):
                c, m, y, k = img.split()
                zeroed_band = k.point(lambda _: 0)
                band = (c, m, y, k)
                if (colorfilter == 'C'):
                        band = (c, zeroed_band, zeroed_band, zeroed_band)
                if (colorfilter == 'M'):
                        band = (zeroed_band, m, zeroed_band, zeroed_band)
                if (colorfilter == 'Y'):
                        band = (zeroed_band, zeroed_band, y, zeroed_band)
                if (colorfilter == 'K'):
                        band = (zeroed_band, zeroed_band, zeroed_band, k)
                img = Image.merge("CMYK", band)
        return img
        
def get_image_modes():
        """ Return list (dictionary) of pillow's standard supported modes """
        modes = {
                '1': '1-bit pixels, black and white, stored with one pixel per byte',
                'L': '8-bit pixels, grayscale',
                'P': '8-bit pixels, mapped to any other mode using a color palette',
                'RGB': '3x8-bit pixels, true color',
                'RGBA': '4x8-bit pixels, true color with transparency mask',
                'CMYK': '4x8-bit pixels, color separation'
        }
        return modes

def validate(fieldname):
        if fieldname is not None:
                fieldname = fieldname.upper()
        if len(fieldname) == 0:
                fieldname = None
        return fieldname

@app.route("/saveimage", methods = ['POST'])
def saveimage():
        """ Modify & save image """
        try:
                imgname = request.form['imgname']
        except:
                pass
        if (imgname == ''  or imgname is None):
                abort(404)
        
        """ Get request params: """
        try:
                colorfilter = validate(request.form['color'])
        except:
                colorfilter = None
        try:
                imgfilter = validate(request.form['filter'])
        except:
                imgfilter = None
        try:
                imgconvert = validate(request.form['convert'])
        except:
                imgconvert = None
        try:
                imgPath = os.path.join(CUR_PATH , APP_IMGBASE, imgname)
                img = Image.open(imgPath)
                imgFormat = img.format
                imgMode = img.mode
                """ mode convertation: """
                if imgconvert is not None:
                        img, imgFormat, imgMode = convert_image_mode(img, imgconvert)
                """ color filter """
                if colorfilter is not None:
                        img = apply_color_filter(img, colorfilter)
                """ blur/sharpen filter: """
                if imgfilter is not None:
                        img = apply_image_filter(img, imgfilter)
                
                filename, fileext = os.path.splitext(imgname)
                if imgconvert is not None:
                        filename = filename + "_" + imgconvert
                if colorfilter is not None:
                        filename += "_"+colorfilter
                if imgfilter is not None:
                        filename += "_"+imgfilter
                fileext = imgFormat.lower()
                imgname = ".".join([filename, fileext])
                imgPath = os.path.join(CUR_PATH , APP_IMGBASE, imgname)
                
                img.save(imgPath, format=imgFormat)
                res = {"result" : imgname }
        except FileNotFoundError:
                res = { "error" : f"Source file {imgname} is unalavaible" }
        except OSError as e:
                res = { "error" : str(e) }
        except SystemError as e:
                res = { "error" : str(e) }
        except Exception as e:
                res = { "error" : str(e) }
        response = make_response(jsonify(res))
        response.headers['Content-Type'] = "application/json"
        return response

@app.route("/deleteimage", methods = ['POST'])
def deleteimage():
        """ Delete image file & connected records from database """
        try:
                imgname = request.form['imgname']
        except:
                pass
        if (imgname == ''  or imgname is None):
                abort(404)
        
        try:
                imgPath = os.path.join(CUR_PATH , APP_IMGBASE, imgname)
                rw = db_delface((imgname,))
                filename, fileext = os.path.splitext(imgname)
                if (os.path.isfile(imgPath) and (fileext[1:].lower() in ALLOWED_EXTENSIONS)):
                        os.remove(imgPath)
                res = {"result" : imgname }
        except sqlite3.Error as e:
                res = { "error" : str(e) }
        except FileNotFoundError:
                res = { "error" : f"Source file {imgname} is unalavaible" }
        except OSError as e:
                res = { "error" : str(e) }
        except SystemError as e:
                res = { "error" : str(e) }
        except Exception as e:
                res = { "error" : str(e) }
        response = make_response(jsonify(res))
        response.headers['Content-Type'] = "application/json"
        return response

@app.route("/loadthumbs", methods = ['GET', 'POST'])
@app.route("/loadthumbs/", methods = ['GET', 'POST'])
@app.route('/loadthumbs/<string:spage>')
def thumbs(spage = None):
        """ Render template 'thumbs.html' contains list of image thumbnails """
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
        cnt = thumb_on_page
        
        if imagescount > 0:
                """ Images count less than count of files: """
                if (cnt > imagescount):
                        page = 0
                        cnt = imagescount
                """ calculate pagescount """
                if ((page * cnt + cnt) > imagescount):
                        page = imagescount // thumb_on_page
                        start = page * cnt
                        cnt = imagescount - (page * thumb_on_page)
                else:
                        start = page * cnt
                end = start + cnt
                previewlist = fileslist[start:end]
                totalpages = int(math.ceil(imagescount / thumb_on_page) - 1)
        else:
                previewlist = []
                start = 0
                end = 0
                totalpages = 0
        previewcount = len(previewlist)
        pages = []
        if totalpages > 0:
                i = 0
                while i <= totalpages:
                        pages.append(i+1)
                        i+=1
        else:
                pages.append(1)
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
def thumb(imgname=''):
        """ Return single image thumbnail or stumb """
        try:
                if (request.method == 'POST'):
                        imgname = request.form['imgname']
                else:
                        imgname = request.args['imgname']
        except:
                pass
        if (imgname == ''  or imgname is None):
                abort(404)
        
        try:
                imgPath = os.path.join(CUR_PATH, APP_IMGBASE, imgname)
                filename, fileext = os.path.splitext(imgname)
                if not os.path.isfile(imgPath) or (fileext[1:].lower() not in ALLOWED_EXTENSIONS):
                        raise Exception(f"Source file {imgname} is unavalaible")
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
        """ Generate thumbnail stumb """
        img = Image.new('RGB', (200,200), color=('#383030'))
        stumb = ImageDraw.Draw(img)
        e = str(e)
        font = ImageFont.truetype(os.path.join(CUR_PATH , APP_STATIC, 'fonts', 'arial.ttf'), size=12)
        stumb.text((10,60), f"Something wrong with {imgname} \n {e}", font=font, fill=('#f40808'))
        return img

@app.route("/saveencoding", methods = ['POST'])
def saveencoding():
        """ Save face encoding into database """
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

def db_delface(args):
        sqlstr = """ DELETE FROM faces 
            WHERE imgname = ?;
        """
        res = db_query(sqlstr, args)
        return res

def  str_to_float_list(s, separator = ', '):
        str_enc_list = s.split(separator)
        if (len(str_enc_list) > 0):
                float_enc_lst = [float(x) for x in str_enc_list]
                return float_enc_lst
                
        return []
        
def to_numpy_array(data):
        return numpy.array(data)

@app.route("/compareface", methods = ['POST'])
def compareface():
        """ Render 'compareface.html' template contains selected face encoding with known faces in database """
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
                known_face_encodings = []
                known_face_imgnames = []
                known_face_comments = []
                face_encoding = to_numpy_array(str_to_float_list(faceenc))
                """ get known faces from database """
                faces = db_fetch("SELECT imgname, faceenc, fcomment FROM faces;")
                if (len(faces) != 0):
                        for face in faces:
                                print(face[0])
                                known_face_enc = to_numpy_array(str_to_float_list(face[1]))
                                known_face_encodings.append(known_face_enc)
                                known_face_imgnames.append(face[0])
                                known_face_comments.append(face[2])
                        matches = face_recognition.compare_faces(known_face_encodings, face_encoding)
                        face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
                        best_match_index = numpy.argmin(face_distances)
                        if True in matches:
                                for index, value in enumerate(matches):
                                        if True == value:
                                                tmp_match_img = {}
                                                tmp_match_img['imgname'] = known_face_imgnames[index]
                                                tmp_match_img['comment'] = known_face_comments[index] if len(known_face_comments[index])>0 else "(empty)"
                                                tmp_match_img['distance'] = round(face_distances[index], 6)
                                                tmp_match_img['coincidence'] = round(((1 - face_distances[index])*100), 2)
                                                tmp_match_img['is_best'] = True if index == best_match_index else False
                                                tmp_match_img['is_same'] = True if tmp_match_img['imgname'] == imgname else False
                                                face_matches[tmp_match_img['imgname']] = tmp_match_img
                
        templateData = {
                'facematches' : face_matches,
                'matchcount' : len(face_matches),
                'total': len(faces),
        }
        return render_template('compareface.html', **templateData)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(BadRequest)
def handle_bad_request(e):
    return 'bad request!', 400

if __name__ == "__main__":
    app.run(host=APP_HOST, port=APP_PORT, debug=APP_DEBUG)
