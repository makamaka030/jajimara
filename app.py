from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3
import random
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "secretkey123"

# 🌟 추가: 프로필 이미지 저장 폴더 설정
UPLOAD_FOLDER = "static/profiles"
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
# 🌟 기본 프로필 이미지 설정 (파일이 없을 경우)
DEFAULT_PROFILE = "default_profile.png" 

# # --- DB 초기화 ---
def init_db():
    conn = sqlite3.connect("gacha.db")
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            gold INTEGER DEFAULT 100,
            nickname TEXT,
            intro TEXT,
            profile_image TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# --- 가챠 확률표 (등급명 정리 및 합계 1.0 확인) ---
GACHA_TABLE = [
    # 확률 합계: 0.01 + 0.04 + 0.25 + 0.70 = 1.00
    ("형님수", 0.01),
    ("킹냥이", 0.04),
    ("냥이", 0.25),
    ("은교", 0.70), # 🌟 (주석 추가: 기존 N 대신 사용된 등급)
]

def roll_gacha():
    rand = random.random()
    cumulative = 0.0
    for rarity, prob in GACHA_TABLE:
        cumulative += prob
        if rand <= cumulative:
            return rarity
    # 🌟 개선: 확률 총합이 1.0이므로 이 부분은 도달하지 않아야 합니다.
    # 안전성을 위해 마지막 요소를 반환하도록 처리 (기존의 'N' 반환 제거)
    return GACHA_TABLE[-1][0] 


# --- 메인 페이지 (POST 요청에서 가챠 로직만 처리) ---
@app.route("/", methods=["GET", "POST"])
def index():
    if "user" not in session:
        return redirect(url_for("login"))

    username = session["user"]

    conn = sqlite3.connect("gacha.db")
    cur = conn.cursor()
    
    cur.execute("SELECT nickname, gold, profile_image FROM users WHERE username=?", (username,))
    user_data = cur.fetchone()
    
    if user_data is None:
        conn.close()
        session.pop("user", None)
        return redirect(url_for("login"))

    nickname = user_data[0]
    gold = user_data[1]
    profile_image = user_data[2]

    result = None

    if request.method == "POST":
        cost = 0
        num_rolls = 0
        
        # 'type' 필드는 index.html의 가챠 폼에서만 전송됩니다.
        if request.form.get("type") == "one":
            cost = 10
            num_rolls = 1
        
        elif request.form.get("type") == "ten":
            cost = 90
            num_rolls = 10
        
        else:
            # 🌟 개선: 타입이 없으면 잘못된 요청 대신 바로 render를 하거나 (GET 요청처럼)
            # 확실하게 오류를 띄웁니다. 여기서는 오류 처리로 유지합니다.
            conn.close()
            return "잘못된 가챠 요청입니다." 

        # 가챠 실행 로직
        if gold < cost:
            result = "❌ G가 부족합니다!"
        else:
            new_gold = gold - cost
            cur.execute("UPDATE users SET gold=? WHERE username=?", (new_gold, username))
            conn.commit()
            gold = new_gold
            
            if num_rolls == 1:
                 result = roll_gacha()
            else:
                 result = [roll_gacha() for _ in range(num_rolls)]
             
    conn.close()

    return render_template("index.html", result=result, gold=gold, nickname=nickname, profile_image=profile_image)


# 🌟 1G 획득 라우트
@app.route("/earn_gold", methods=["POST"])
def earn_gold():
    if "user" not in session:
        return redirect(url_for("login"))
    
    username = session["user"]
    
    conn = sqlite3.connect("gacha.db")
    cur = conn.cursor()
    
    # 트랜잭션 안전성을 위해 SELECT 후 UPDATE
    cur.execute("SELECT gold FROM users WHERE username=?", (username,))
    user_data = cur.fetchone()

    if user_data:
        current_gold = user_data[0]
        new_gold = current_gold + 1
        
        cur.execute("UPDATE users SET gold=? WHERE username=?", (new_gold, username))
        conn.commit()
    
    conn.close()
    
    return redirect(url_for("index"))


# --- 회원가입 ---
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        nickname = request.form["nickname"] 

        conn = sqlite3.connect("gacha.db")
        cur = conn.cursor()

        try:
            cur.execute("INSERT INTO users (username, password, gold, nickname, intro, profile_image) VALUES (?, ?, 100, ?, '', ?)",
                         (username, password, nickname, DEFAULT_PROFILE))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return "이미 존재하는 아이디입니다!"
        except Exception as e:
            conn.close()
            return f"회원가입 오류 발생: {e}"

        conn.close()
        return redirect(url_for("login"))

    return render_template("register.html")


# --- 로그인 ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect("gacha.db")
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        user = cur.fetchone()
        conn.close()

        if user:
            session["user"] = username
            return redirect(url_for("index"))
        else:
            return "로그인 실패: ID 또는 PW 오류"

    return render_template("login.html")


# --- 로그아웃 ---
@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

# --- 마이 페이지 ---
@app.route("/mypage", methods=["GET", "POST"])
def mypage():
    if "user" not in session:
        return redirect(url_for("login"))

    username = session["user"]
    
    conn = sqlite3.connect("gacha.db")
    cur = conn.cursor()

    if request.method == "POST":
        new_nickname = request.form["nickname"]
        new_intro = request.form["intro"]
        
        file = request.files.get("profile_image")
        new_profile_image_name = None

        if file and file.filename:
            filename = secure_filename(file.filename)
            unique_filename = f"{username}_{filename}" 
            save_path = os.path.join(UPLOAD_FOLDER, unique_filename)
            file.save(save_path)
            new_profile_image_name = unique_filename
        
        if new_profile_image_name:
            cur.execute("UPDATE users SET nickname=?, intro=?, profile_image=? WHERE username=?",
                        (new_nickname, new_intro, new_profile_image_name, username))
        else:
            cur.execute("UPDATE users SET nickname=?, intro=? WHERE username=?",
                        (new_nickname, new_intro, username))
        
        conn.commit()
        conn.close()
        return redirect(url_for("mypage")) 

    cur.execute("SELECT username, gold, nickname, intro, profile_image FROM users WHERE username=?", (username,))
    user_data = cur.fetchone()
    conn.close()

    if user_data is None:
        session.pop("user", None)
        return redirect(url_for("login"))

    user = {
        "username": user_data[0],
        "gold": user_data[1],
        "nickname": user_data[2],
        "intro": user_data[3],
        "profile_image": user_data[4]
    }
    
    return render_template("mypage.html", user=user)


if __name__ == "__main__":
    app.run(debug=True)
