import os
import secrets
from PIL import Image
from flask import current_app

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def delete_old_image(image_path):
    if image_path:
        full_path = os.path.join(current_app.root_path, 'static', 'uploads', image_path)
        if os.path.exists(full_path):
            os.remove(full_path)

def save_image(form_image, folder, size=(200, 200)):
    # generate random filename
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_image.filename)
    filename = random_hex + f_ext

    # ensure upload folder exists
    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', folder)
    os.makedirs(upload_dir, exist_ok=True)

    # resize & save
    img = Image.open(form_image)
    img.thumbnail(size)
    filepath = os.path.join(upload_dir, filename)
    img.save(filepath)

    # return path relative to /static/uploads/
    return f"{folder}/{filename}"
