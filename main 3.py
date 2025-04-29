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

# Модели
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

    # Уникальное ограничение, чтобы пользователь мог поставить только один лайк на пост
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

# Базовый шаблон
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
            notification.className = `fixed top-4 right-4 p-4 rounded-md shadow-md ${type === 'success' ? 'bg-green-500' : 'bg-red-500'} text-white`;
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

        function likePost(postId) {
            fetch(`/like/${postId}`, {
                method: 'POST'
            })
            .then(response => response.json())
            .then(data => {
                if(data.success) {
                    const likeCount = document.getElementById(`like-count-${postId}`);
                    likeCount.textContent = data.likes;

                    const likeBtn = document.getElementById(`like-btn-${postId}`);
                    if(data.liked) {
                        likeBtn.innerHTML = '<i class="fas fa-heart text-red-500"></i>';
                    } else {
                        likeBtn.innerHTML = '<i class="far fa-heart"></i>';
                    }
                }
            });
        }
    </script>
</head>
<body class="bg-gray-100 text-gray-900">
    <div class="max-w-3xl mx-auto py-8 px-4">
        <div class="mb-6 flex justify-between items-center">
            <h1 class="text-3xl font-bold text-blue-600"><a href='{{ url_for('index') }}'>NerestReddit</a></h1>
            {% if session.get('username') %}
                <div class="space-x-4">
                    <span class="text-gray-700">Привет, {{ session['username'] }}!</span>
                    <a href="{{ url_for('create_post') }}" class="text-blue-500 hover:underline">Создать пост</a>
                    <a href="{{ url_for('logout') }}" class="text-red-500 hover:underline">Выйти</a>
                </div>
            {% endif %}
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
        <div class='bg-white rounded-xl p-4 shadow mb-4'>
            <h2 class='text-xl font-semibold text-blue-700'><a href='{url_for('view_post', post_id=post.id)}'>{post.title}</a></h2>
            <p class='mt-2'>{post.content}</p>
            <div class='flex justify-between items-center mt-4'>
                <p class='text-sm text-gray-500'>Автор: {post.author} | {post.created_at.strftime('%d.%m.%Y %H:%M')}</p>
                <div class='flex items-center'>
                    <button id="like-btn-{post.id}" onclick="likePost({post.id})" class="mr-1 text-gray-600 hover:text-red-500">
                        <i class="{'fas text-red-500' if user_liked_post(post.id) else 'far'} fa-heart"></i>
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
            db.session.add(User(username=username, password=hashed_pw))
            db.session.commit()

            # Создаем уведомление об успешной регистрации
            notification = {"message": "Аккаунт успешно создан! Теперь вы можете войти.", "type": "success"}
            return render_template_string(
                base_html, 
                title="Регистрация", 
                content=render_login_form(""), 
                notification=notification
            )

    return render_template_string(base_html, title="Регистрация", content=render_register_form(error))

def render_register_form(error):
    return f"""
    <div class="bg-white p-6 rounded-xl shadow-md max-w-md mx-auto">
        <h2 class="text-xl font-bold mb-4">Регистрация</h2>
        {"<p class='text-red-500 mb-2'>" + error + "</p>" if error else ""}
        <form method="post" class="space-y-4">
            <input name="username" class="w-full p-2 border rounded" placeholder="Имя пользователя">
            <input type="password" name="password" class="w-full p-2 border rounded" placeholder="Пароль">
            <button class="bg-blue-500 text-white px-4 py-2 rounded w-full">Зарегистрироваться</button>
        </form>
        <p class="mt-4 text-sm text-gray-600">Уже есть аккаунт? <a href="{url_for('login')}" class="text-blue-500 underline">Войти</a></p>
    </div>
    """

def render_login_form(error):
    return f"""
    <div class="bg-white p-6 rounded-xl shadow-md max-w-md mx-auto">
        <h2 class="text-xl font-bold mb-4">Вход</h2>
        {"<p class='text-red-500 mb-2'>" + error + "</p>" if error else ""}
        <form method="post" class="space-y-4">
            <input name="username" class="w-full p-2 border rounded" placeholder="Имя пользователя">
            <input type="password" name="password" class="w-full p-2 border rounded" placeholder="Пароль">
            <button class="bg-blue-500 text-white px-4 py-2 rounded w-full">Войти</button>
        </form>
        <p class="mt-4 text-sm text-gray-600">Нет аккаунта? <a href="{url_for('register')}" class="text-blue-500 underline">Зарегистрироваться</a></p>
    </div>
    """

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = ""
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['username'] = user.username
            return redirect(url_for('index'))
        else:
            error = "Неверные имя пользователя или пароль."

    return render_template_string(base_html, title="Вход", content=render_login_form(error))

@app.route('/logout')
def logout():
    session.pop('username', None)
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
            # Вот исправление - вместо вызова .get_data() у результата index(),
            # мы просто делаем редирект на главную страницу
            return redirect(url_for('index'))

    form = f"""
    <div class="bg-white p-6 rounded-xl shadow-md max-w-md mx-auto">
        <h2 class="text-xl font-bold mb-4">Новый пост</h2>
        {"<p class='text-red-500 mb-2'>" + error + "</p>" if error else ""}
        <form method="post" class="space-y-4">
            <input name="title" class="w-full p-2 border rounded" placeholder="Заголовок">
            <textarea name="content" class="w-full p-2 border rounded h-32" placeholder="Содержание..."></textarea>
            <button class="bg-green-500 text-white px-4 py-2 rounded w-full">Опубликовать</button>
        </form>
    </div>
    """
    return render_template_string(base_html, title="Создать пост", content=form, notification=notification)

@app.route('/post/<int:post_id>')
def view_post(post_id):
    if not is_logged_in():
        return redirect(url_for('login'))

    post = Post.query.get_or_404(post_id)
    comments = Comment.query.filter_by(post_id=post_id).order_by(Comment.created_at).all()

    comments_html = "".join(
        f"""
        <div class="border-t pt-3 pb-3">
            <div class="flex items-center">
                <span class="font-medium">{comment.author}</span>
                <span class="text-xs text-gray-500 ml-2">{comment.created_at.strftime('%d.%m.%Y %H:%M')}</span>
            </div>
            <p class="mt-1">{comment.content}</p>
        </div>
        """ for comment in comments
    )

    content = f"""
    <div class="bg-white rounded-xl p-6 shadow mb-4">
        <h1 class="text-2xl font-bold text-blue-700 mb-2">{post.title}</h1>
        <p class="mb-4">{post.content}</p>
        <div class="flex justify-between items-center mb-6">
            <p class="text-sm text-gray-500">Автор: {post.author} | {post.created_at.strftime('%d.%m.%Y %H:%M')}</p>
            <div class="flex items-center">
                <button id="like-btn-{post.id}" onclick="likePost({post.id})" class="mr-1 text-gray-600 hover:text-red-500">
                    <i class="{'fas text-red-500' if user_liked_post(post.id) else 'far'} fa-heart"></i>
                </button>
                <span id="like-count-{post.id}" class="text-gray-600">{post.likes}</span>
            </div>
        </div>

        <div class="mt-8">
            <h3 class="text-xl font-semibold mb-4">Комментарии</h3>
            <div class="mb-6">
                <form action="{url_for('add_comment', post_id=post.id)}" method="post" class="flex flex-col gap-2">
                    <textarea name="content" class="w-full p-2 border rounded h-24" placeholder="Добавить комментарий..."></textarea>
                    <button class="bg-blue-500 text-white px-4 py-2 rounded self-end">Отправить</button>
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
    if content:
        comment = Comment(
            content=content,
            author=session['username'],
            post_id=post_id
        )
        db.session.add(comment)
        db.session.commit()

    return redirect(url_for('view_post', post_id=post_id))

@app.route('/like/<int:post_id>', methods=['POST'])
def like_post(post_id):
    if not is_logged_in():
        return jsonify({"success": False, "error": "Необходимо войти"}), 401

    user_id = get_user_id()
    post = Post.query.get_or_404(post_id)

    # Проверяем, ставил ли пользователь лайк
    like = Like.query.filter_by(user_id=user_id, post_id=post_id).first()

    if like:
        # Если лайк уже есть - удаляем его
        db.session.delete(like)
        post.likes -= 1
        liked = False
    else:
        # Если лайка нет - добавляем
        new_like = Like(user_id=user_id, post_id=post_id)
        db.session.add(new_like)
        post.likes += 1
        liked = True

    db.session.commit()

    return jsonify({"success": True, "likes": post.likes, "liked": liked})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)