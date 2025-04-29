from flask import Flask, request, redirect, url_for, session, render_template_string, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'super_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///nerestreddit.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    author = db.Column(db.String(80), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    likes = db.Column(db.Integer, default=0)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    author = db.Column(db.String(80), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    replies = db.relationship('Comment', backref=db.backref('parent', remote_side=[id]), lazy='dynamic')

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

    # Unique constraint to ensure a user can like a post only once
    __table_args__ = (db.UniqueConstraint('user_id', 'post_id'),)

def is_logged_in():
    return 'username' in session

def get_user_id():
    if is_logged_in():
        user = User.query.filter_by(username=session['username']).first()
        if user:
            return user.id
    return None

def user_liked_post(post_id):
    user_id = get_user_id()
    if user_id:
        like = Like.query.filter_by(user_id=user_id, post_id=post_id).first()
        return like is not None
    return False

# Base template with dark blue theme
base_html = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>{{ title }}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
    <script>
        function showNotification(message, type) {
            const notification = document.createElement('div');
            notification.className = `fixed top-4 right-4 p-4 rounded-md shadow-md ${type === 'success' ? 'bg-blue-500' : 'bg-red-500'} text-white`;
            notification.textContent = message;
            document.body.appendChild(notification);

            setTimeout(() => {
                notification.style.opacity = '0';
                notification.style.transition = 'opacity 0.5s';
                setTimeout(() => {
                    document.body.removeChild(notification);
                }, 500);
            }, 3000);
        }

        {% if notification %}
            document.addEventListener('DOMContentLoaded', function() {
                showNotification("{{ notification.message }}", "{{ notification.type }}");
            });
        {% endif %}

        async function likePost(postId) {
            try {
                const response = await fetch(`/like/${postId}`, {
                    method: 'POST'
                });
                const data = await response.json();
                if (data.success) {
                    const likeCount = document.getElementById(`like-count-${postId}`);
                    likeCount.textContent = data.likes;

                    const likeBtn = document.getElementById(`like-btn-${postId}`);
                    if (data.liked) {
                        likeBtn.innerHTML = '<i class="fas fa-heart text-blue-500"></i>';
                    } else {
                        likeBtn.innerHTML = '<i class="far fa-heart"></i>';
                    }
                } else if (data.error === "Необходимо войти") {
                    window.location.href = "/login";
                }
            } catch (error) {
                console.error('Error liking post:', error);
            }
        }

        function toggleReplyForm(commentId) {
            const replyForm = document.getElementById(`reply-form-${commentId}`);
            replyForm.classList.toggle('hidden');
        }
    </script>
    <style>
        body {
            background-color: #0f172a; /* dark blue */
            color: #e2e8f0;
        }
        .bg-white {
            background-color: #1e3a8a; /* darker blue */
        }
        .text-gray-900 {
            color: #e2e8f0;
        }
        .text-gray-500 {
            color: #94a3b8;
        }
        .text-gray-600 {
            color: #cbd5e1;
        }
        .border-gray-200 {
            border-color: #334155;
        }
        input, textarea, button {
            background-color: #1e3a8a;
            color: #e2e8f0;
            border-color: #334155;
        }
        input::placeholder, textarea::placeholder {
            color: #94a3b8;
        }
        a {
            color: #3b82f6;
        }
        a:hover {
            text-decoration: underline;
        }
        .post-container {
            background-color: #1e3a8a;
            border: 1px solid #334155;
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 16px;
        }
        .post-title {
            color: #60a5fa;
        }
        .post-content {
            color: #e2e8f0;
        }
        .comment-container {
            background-color: #1e40af;
            border: 1px solid #2563eb;
            border-radius: 8px;
            padding: 16px;
            margin-top: 8px;
        }
        .comment-content {
            color: #e2e8f0;
        }
    </style>
</head>
<body class="bg-gray-900 text-gray-100">
    <div class="max-w-3xl mx-auto py-8 px-4">
        <div class="mb-6 flex justify-between items-center">
            <h1 class="text-3xl font-bold text-blue-500"><a href='{{ url_for('index') }}'>NerestReddit</a></h1>
            <div class="space-x-4">
                {% if session.get('username') %}
                    <span class="text-blue-300">Привет, {{ session['username'] }}!</span>
                    <a href="{{ url_for('create_post') }}" class="text-blue-500 hover:underline">Создать пост</a>
                    <a href="{{ url_for('logout') }}" class="text-blue-500 hover:underline">Выйти</a>
                {% else %}
                    <a href="{{ url_for('login') }}" class="text-blue-500 hover:underline">Войти</a>
                    <a href="{{ url_for('register') }}" class="text-blue-500 hover:underline">Регистрация</a>
                {% endif %}
            </div>
        </div>
        {{ content | safe }}
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    if not is_logged_in():
        return redirect(url_for('login'))
    posts = Post.query.order_by(Post.created_at.desc()).all()
    posts_html = "".join(
        f"""
        <div class='post-container'>
            <h2 class='text-xl font-semibold post-title'><a href='{url_for('view_post', post_id=post.id)}'>{post.title}</a></h2>
            <p class='mt-2 post-content'>{post.content}</p>
            <div class='flex justify-between items-center mt-4'>
                <p class='text-sm text-gray-500'>Автор: {post.author} | {post.created_at.strftime('%d.%m.%Y %H:%M')}</p>
                <div class='flex items-center'>
                    <button id="like-btn-{post.id}" onclick="likePost({post.id})" class="mr-1 text-gray-600 hover:text-blue-500">
                        <i class="{'fas text-blue-500' if user_liked_post(post.id) else 'far'} fa-heart"></i>
                    </button>
                    <span id="like-count-{post.id}" class="text-gray-600">{post.likes}</span>
                    <a href="{url_for('view_post', post_id=post.id)}" class="ml-4 text-blue-500 hover:underline">
                        Комментарии
                    </a>
                </div>
            </div>
        </div>
        """ for post in posts
    )
    return render_template_string(base_html, title="Главная", content=posts_html)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if is_logged_in():
        return redirect(url_for('index'))
        
    error = ""
    notification = None

    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()

        if not username or not password:
            error = "Пожалуйста, заполните все поля."
        elif User.query.filter_by(username=username).first():
            error = "Пользователь уже существует."
        else:
            hashed_pw = generate_password_hash(password)
            new_user = User(username=username, password=hashed_pw)
            db.session.add(new_user)
            db.session.commit()

            # Automatically log in the user after registration
            session['username'] = new_user.username
            notification = {"message": "Аккаунт успешно создан!", "type": "success"}
            return redirect(url_for('index'))

    return render_template_string(base_html, title="Регистрация", content=render_register_form(error), notification=notification)

def render_register_form(error):
    return f"""
    <div class="bg-white p-6 rounded-xl shadow-md max-w-md mx-auto">
        <h2 class="text-xl font-bold mb-4">Регистрация</h2>
        {"<p class='text-red-500 mb-2'>" + error + "</p>" if error else ""}
        <form method="post" class="space-y-4">
            <input name="username" class="w-full p-2 border rounded bg-blue-900 text-gray-200" placeholder="Имя пользователя">
            <input type="password" name="password" class="w-full p-2 border rounded bg-blue-900 text-gray-200" placeholder="Пароль">
            <button class="bg-blue-500 text-white px-4 py-2 rounded w-full hover:bg-blue-600">Зарегистрироваться</button>
        </form>
        <p class="mt-4 text-sm text-gray-400">Уже есть аккаунт? <a href="{url_for('login')}" class="text-blue-500 underline">Войти</a></p>
    </div>
    """

def render_login_form(error):
    return f"""
    <div class="bg-white p-6 rounded-xl shadow-md max-w-md mx-auto">
        <h2 class="text-xl font-bold mb-4">Вход</h2>
        {"<p class='text-red-500 mb-2'>" + error + "</p>" if error else ""}
        <form method="post" class="space-y-4">
            <input name="username" class="w-full p-2 border rounded bg-blue-900 text-gray-200" placeholder="Имя пользователя">
            <input type="password" name="password" class="w-full p-2 border rounded bg-blue-900 text-gray-200" placeholder="Пароль">
            <button class="bg-blue-500 text-white px-4 py-2 rounded w-full hover:bg-blue-600">Войти</button>
        </form>
        <p class="mt-4 text-sm text-gray-400">Нет аккаунта? <a href="{url_for('register')}" class="text-blue-500 underline">Зарегистрироваться</a></p>
    </div>
    """

@app.route('/login', methods=['GET', 'POST'])
def login():
    if is_logged_in():
        return redirect(url_for('index'))
        
    error = ""
    notification = None
    
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        
        if not username or not password:
            error = "Пожалуйста, заполните все поля."
        else:
            user = User.query.filter_by(username=username).first()
            if user and check_password_hash(user.password, password):
                session['username'] = user.username
                notification = {"message": "Успешный вход!", "type": "success"}
                return redirect(url_for('index'))
            else:
                error = "Неверные имя пользователя или пароль."

    return render_template_string(base_html, title="Вход", content=render_login_form(error), notification=notification)

@app.route('/logout')
def logout():
    if 'username' in session:
        session.pop('username', None)
        # Использование flask.flash требует конфигурации приложения,
        # поэтому мы используем перенаправление с уведомлением через параметр запроса
        return redirect(url_for('login') + '?logged_out=1')
    return redirect(url_for('login'))

@app.route('/create', methods=['GET', 'POST'])
def create_post():
    if not is_logged_in():
        return redirect(url_for('login'))
    error = ""
    notification = None

    if request.method == 'POST':
        title = request.form['title'].strip()
        content = request.form['content'].strip()
        if not title or not content:
            error = "Заполните все поля."
        else:
            post = Post(title=title, content=content, author=session['username'])
            db.session.add(post)
            db.session.commit()
            notification = {"message": "Пост успешно создан!", "type": "success"}
            return redirect(url_for('index'))

    form = f"""
    <div class="bg-white p-6 rounded-xl shadow-md max-w-md mx-auto">
        <h2 class="text-xl font-bold mb-4">Новый пост</h2>
        {"<p class='text-red-500 mb-2'>" + error + "</p>" if error else ""}
        <form method="post" class="space-y-4">
            <input name="title" class="w-full p-2 border rounded bg-blue-900 text-gray-200" placeholder="Заголовок">
            <textarea name="content" class="w-full p-2 border rounded h-32 bg-blue-900 text-gray-200" placeholder="Содержание..."></textarea>
            <button class="bg-blue-500 text-white px-4 py-2 rounded w-full hover:bg-blue-600">Опубликовать</button>
        </form>
    </div>
    """
    return render_template_string(base_html, title="Создать пост", content=form, notification=notification)

@app.route('/post/<int:post_id>')
def view_post(post_id):
    if not is_logged_in():
        return redirect(url_for('login'))

    post = Post.query.get_or_404(post_id)
    comments = Comment.query.filter_by(post_id=post_id, parent_id=None).order_by(Comment.created_at).all()

    def render_comments(comments):
        comments_html = ""
        for comment in comments:
            replies = Comment.query.filter_by(parent_id=comment.id).order_by(Comment.created_at).all()
            replies_html = render_comments(replies) if replies else ""
            comments_html += f"""
            <div class="comment-container">
                <div class="flex items-center">
                    <span class="font-medium">{comment.author}</span>
                    <span class="text-xs text-gray-500 ml-2">{comment.created_at.strftime('%d.%m.%Y %H:%M')}</span>
                </div>
                <p class="mt-1 comment-content">{comment.content}</p>
                <div class="ml-4 mt-2">
                    <a href="#" onclick="toggleReplyForm({comment.id}); return false;" class="text-blue-500 hover:underline text-sm">Ответить</a>
                    <div id="reply-form-{comment.id}" class="hidden mt-2">
                        <form action="{url_for('add_comment', post_id=post.id)}" method="post" class="flex flex-col gap-2">
                            <input type="hidden" name="parent_id" value="{comment.id}">
                            <textarea name="content" class="w-full p-2 border rounded h-24 bg-blue-900 text-gray-200" placeholder="Добавить ответ..."></textarea>
                            <button class="bg-blue-500 text-white px-4 py-2 rounded self-end hover:bg-blue-600">Отправить</button>
                        </form>
                    </div>
                </div>
                <div class="ml-4 mt-2">
                    {replies_html}
                </div>
            </div>
            """
        return comments_html

    comments_html = render_comments(comments)

    content = f"""
    <div class="post-container">
        <h1 class="text-2xl font-bold post-title mb-2">{post.title}</h1>
        <p class="mb-4 post-content">{post.content}</p>
        <div class="flex justify-between items-center mb-6">
            <p class="text-sm text-gray-500">Автор: {post.author} | {post.created_at.strftime('%d.%m.%Y %H:%M')}</p>
            <div class="flex items-center">
                <button id="like-btn-{post.id}" onclick="likePost({post.id})" class="mr-1 text-gray-600 hover:text-blue-500">
                    <i class="{'fas text-blue-500' if user_liked_post(post.id) else 'far'} fa-heart"></i>
                </button>
                <span id="like-count-{post.id}" class="text-gray-600">{post.likes}</span>
            </div>
        </div>

        <div class="mt-8">
            <h3 class="text-xl font-semibold mb-4">Комментарии</h3>
            <div class="mb-6">
                <form action="{url_for('add_comment', post_id=post.id)}" method="post" class="flex flex-col gap-2">
                    <textarea name="content" class="w-full p-2 border rounded h-24 bg-blue-900 text-gray-200" placeholder="Добавить комментарий..."></textarea>
                    <button class="bg-blue-500 text-white px-4 py-2 rounded self-end hover:bg-blue-600">Отправить</button>
                </form>
            </div>
            <div class="space-y-4">
                {comments_html if comments else "<p class='text-gray-500'>Пока нет комментариев</p>"}
            </div>
        </div>
    </div>
    """

    return render_template_string(base_html, title=post.title, content=content)

@app.route('/post/<int:post_id>/comment', methods=['POST'])
def add_comment(post_id):
    if not is_logged_in():
        return redirect(url_for('login'))

    content = request.form['content'].strip()
    parent_id = request.form.get('parent_id')
    
    if not content:
        return redirect(url_for('view_post', post_id=post_id))
    
    # Проверка существования поста
    post = Post.query.get_or_404(post_id)
    
    # Проверка существования родительского комментария, если он указан
    if parent_id:
        parent_comment = Comment.query.get(parent_id)
        if not parent_comment or parent_comment.post_id != post_id:
            return redirect(url_for('view_post', post_id=post_id))
    
    comment = Comment(
        content=content,
        author=session['username'],
        post_id=post_id,
        parent_id=parent_id
    )
    db.session.add(comment)
    db.session.commit()

    return redirect(url_for('view_post', post_id=post_id))

@app.route('/like/<int:post_id>', methods=['POST'])
def like_post(post_id):
    if not is_logged_in():
        return jsonify({"success": False, "error": "Необходимо войти"}), 401

    user_id = get_user_id()
    if not user_id:
        return jsonify({"success": False, "error": "Пользователь не найден"}), 401
    
    post = Post.query.get_or_404(post_id)

    # Check if the user has already liked the post
    like = Like.query.filter_by(user_id=user_id, post_id=post_id).first()

    if like:
        # If the like exists, remove it
        db.session.delete(like)
        post.likes -= 1
        liked = False
    else:
        # If the like does not exist, add it
        new_like = Like(user_id=user_id, post_id=post_id)
        db.session.add(new_like)
        post.likes += 1
        liked = True

    db.session.commit()

    return jsonify({"success": True, "likes": post.likes, "liked": liked})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)), debug=True)
