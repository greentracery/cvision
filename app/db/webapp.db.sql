CREATE TABLE IF NOT EXISTS faces(
            faceid INTEGER PRIMARY KEY AUTOINCREMENT,
            imgname TEXT NOT NULL,
            imgtop INTEGER NOT NULL,
            imgright INTEGER NOT NULL,
            imgbottom INTEGER NOT NULL,
            imgleft INTEGER NOT NULL,
            faceenc TEXT NOT NULL,
            fcomment TEXT DEFAULT NULL);
