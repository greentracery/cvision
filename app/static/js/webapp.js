const loadthumbs = async (page) => {
        let preview = document.getElementById("thumb-preview");
        let url = srv + '/loadthumbs/' + page;
        preview.innerHTML = await getData(url);
        return false;
}

const loadcontent = async (img, data=null, ispost=false) => {
        let loader = '<div class="loader"></div>';
        let workimage = document.getElementById("workimage");
        let facefinder = document.getElementById("facefinder");
        workimage.innerHTML = loader;
        facefinder.innerHTML = loader;
        let url = srv + '/loadworkimage/' + img;
        let url2 = srv + '/loadfacefider/' + img;
        workimage.innerHTML = await getData(url, data, ispost);
        facefinder.innerHTML = await getData(url2, data, ispost);
        return false;
}

const params2url = (url, data) => {
        let params = new Array();
        switch (data.constructor) {
                case Array:
                        for (let k in data) {
                                params.push(data[k]);
                        }
                        url+=('?' + params.join('&'));
                break;
                case Object:
                        for (let k in data) {
                                params.push( k + '=' + data[k] );
                        }
                        url+=('?' + params.join('&'));
                break;
                case Number:
                        url+=('?'+ data);
                break;
                case String:
                        url+=('?'+ data);
                break;
        }
        url = encodeURI(url);
        return url;
}

const getData = async (url, data=null, ispost=false, isjson = false) => {
        let METHOD = (ispost)? "POST" : "GET";
        let request_params = {};
        request_params.method = METHOD;
        if (data !== null){
                if(ispost){
                        request_params.body = data;
                }else{
                        url = params2url(url, data);
                }
        }
        try{
                let response = await fetch(url, request_params);
                if(!response.ok) {
                        throw new Error(`${url} url unavalaible, http status: ${response.status}` );
                }
                if(isjson){ 
                       return await response.json();
                }else{
                        return await response.text();
                }
        }catch(e){
                error = { "error" : e.message };
                return (isjson)? error : JSON.stringify(error);
        }
}

const showencodind = (faceid) => {
        let encodingWrapper = document.getElementById("face-encoding-wrapper-"+faceid);
        //encodingWrapper.style.visibility = 'visible';
        encodingWrapper.style.display = 'inline-block';
}

const hideencodind = (faceid) => {
        let encodingWrapper = document.getElementById("face-encoding-wrapper-"+faceid);
        //encodingWrapper.style.visibility = 'hidden';
        encodingWrapper.style.display = 'none';
}

const saveasknown = (faceid) => {
        let posWrapper = document.getElementById("face-pos-wrapper-"+faceid);
        posWrapper.style.display = 'inline-block';
}

const savecancel = (faceid) => {
        let posWrapper = document.getElementById("face-pos-wrapper-"+faceid);
        posWrapper.style.display = 'none';
}

const filterimage = (img) => {
        try{
                let upf = document.forms['img-filter-form'];
                let formData = new FormData(upf);
                let params = {};
                for(let [name, value] of formData) {
                        params[name] = value;
                }
                let workimage = document.getElementById("workimage-preview");
                let url = params2url(srv + '/image/' + img, params);
                workimage.src = url;
        }catch(e){ console.error(e.message);}
        return false;
}

const togglezoom = (obj) => {
        if(obj.style.width == '' && obj.style['z-index'] == ''){
                obj.style.width = 'auto';
                obj.style['z-index'] = '1000';
                obj.style.position = 'relative';
                obj.style.top = '10px';
                obj.style.left = '30px';
                
        }else{
                obj.style.width = '';
                obj.style['z-index'] = '';
                obj.style.position = '';
        }
}

const savefacedata = async (faceid, imgname) => {
        let face = {};
        face.imgname = imgname;
        face.faceenc = document.getElementById('face-encoding-'+faceid).value;
        face.imgtop = document.getElementById('face-position-top-'+faceid).value;
        face.imgbottom = document.getElementById('face-position-bottom-'+faceid).value;
        face.imgleft = document.getElementById('face-position-left-'+faceid).value;
        face.imgright = document.getElementById('face-position-right-'+faceid).value;
        face.comment = document.getElementById('face-comment-'+faceid).value;
        fdata = new FormData();
        for (let key in face){
                fdata.append(key, face[key])
        }
        let url = srv + '/saveencoding';
        resp = await getData(url, fdata, true, true);
        //console.log(resp);
        error = getError(resp);
        if(error !== null){
                alert("Ooops! " + error);
                return false;
        }
        result = getResult(resp);
        if(result !== null){
                alert("Done. " + result + " row(s) added successfull");
                let savelogo = document.getElementById('recognized-face-' + faceid).appendChild(document.createElement('h3'));
                savelogo.innerText = '🖬';
                savelogo.title = 'Saved in database';
                savecancel(faceid);
        }
        return false;
}

const getResult = (o) => {
        return(o != null && o.hasOwnProperty('result'))? o.result : null;
}

const getError = (o) => {
        return(o != null && o.hasOwnProperty('error'))? o.error : null;
}

const compareface = async (faceid, imgname) => {
        let face = {};
        face.imgname = imgname;
        face.faceenc = document.getElementById('face-encoding-'+faceid).value;
        face.imgtop = document.getElementById('face-position-top-'+faceid).value;
        face.imgbottom = document.getElementById('face-position-bottom-'+faceid).value;
        face.imgleft = document.getElementById('face-position-left-'+faceid).value;
        face.imgright = document.getElementById('face-position-right-'+faceid).value;
        fdata = new FormData();
        for (let key in face){
                fdata.append(key, face[key])
        }
        let url = srv + '/compareface';
        let comparearea = document.getElementById("comparearea");
        comparearea.innerHTML = await getData(url, fdata, true, false);
        return false;
}
