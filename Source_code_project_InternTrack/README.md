# InternTrack

Ứng dụng quản lý kỳ thực tập gồm backend FastAPI/MySQL và frontend HTML/CSS/JavaScript tĩnh.

## Yêu cầu môi trường

- Python 3.10 trở lên.
- MySQL đang chạy và có quyền tạo/sửa bảng trong database của ứng dụng.
- PowerShell hoặc terminal tương đương.
- Frontend không cần Node.js hay bước build; dùng web server tĩnh để phục vụ các ES module.

Các lệnh dưới đây chạy từ thư mục `Source_code_project_InternTrack` (thư mục chứa README này).

## 1. Tạo database MySQL

Tạo database và tài khoản riêng cho ứng dụng trong MySQL:

```sql
CREATE DATABASE interntrack
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

CREATE USER 'interntrack'@'127.0.0.1' IDENTIFIED BY 'REPLACE_WITH_PRIVATE_PASSWORD';
GRANT ALL PRIVILEGES ON interntrack.* TO 'interntrack'@'127.0.0.1';
```

Nếu database hoặc tài khoản đã tồn tại, không chạy lại các lệnh tạo tương ứng. Không dùng tài khoản MySQL quản trị cho ứng dụng.

## 2. Cài backend và cấu hình môi trường

Tạo virtual environment và cài dependencies:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Tạo `.env` từ mẫu nếu chưa có:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Điền các giá trị riêng tư trong `.env`; không commit file này:

```dotenv
APP_ENV=development
DATABASE_URL=mysql+pymysql://interntrack:REPLACE_WITH_PRIVATE_PASSWORD@127.0.0.1:3306/interntrack?charset=utf8mb4
SECRET_KEY=REPLACE_WITH_RANDOM_SECRET_AT_LEAST_32_CHARACTERS
DEFAULT_ADMIN_PASSWORD=REPLACE_WITH_PRIVATE_DEV_PASSWORD
SAMPLE_USER_PASSWORD=REPLACE_WITH_PRIVATE_SAMPLE_PASSWORD
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
MAX_ATTACHMENT_SIZE_MB=10
ATTACHMENT_STORAGE_DIR=storage/uploads
ALLOWED_ORIGINS=["http://localhost:3000","http://localhost:5173"]
```

Tạo `SECRET_KEY` ngẫu nhiên bằng:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

`SECRET_KEY` phải dài ít nhất 32 ký tự. Mật khẩu seed tối thiểu 8 ký tự và không vượt quá 72 byte UTF-8. Nếu mật khẩu database có ký tự đặc biệt, URL-encode phần mật khẩu trong `DATABASE_URL`.

Các giá trị mặc định và tên biến cấu hình khác được liệt kê trong [.env.example](./.env.example). Hiện CORS trong `app/main.py` cho phép `http://127.0.0.1:5500` và `http://localhost:5500`; biến `ALLOWED_ORIGINS` trong `.env` chưa được dùng để thay đổi danh sách này.

## 3. Schema, migration và dữ liệu seed

Khi backend khởi động, `app.main` gọi SQLAlchemy `Base.metadata.create_all()` để tạo các bảng còn thiếu. Lệnh này **không cập nhật cấu trúc của bảng đã tồn tại**.

- Database mới dùng model hiện tại: khởi động backend một lần để tạo schema; không chạy migration attachment bên dưới.
- Database cũ đã có bảng `attachments`: trước khi khởi động backend mới, kiểm tra `SHOW COLUMNS FROM attachments;`. Nếu thiếu `stored_filename`, `mime_type` hoặc `file_size`, chạy migration [20261117_add_attachment_metadata.sql](./migrations/20261117_add_attachment_metadata.sql) đúng một lần từ thư mục dự án:

  ```text
  mysql -h 127.0.0.1 -P 3306 -u interntrack -p interntrack
  mysql> source migrations/20261117_add_attachment_metadata.sql;
  ```

  Migration hiện không idempotent; không chạy lại nếu các cột đã có.

Sau khi schema đã được tạo (hoặc migration database cũ đã chạy), có thể seed tài khoản ADMIN development:

```powershell
python -m app.db.seed_admin
```

Script chỉ chạy khi `APP_ENV=development`, dùng `DEFAULT_ADMIN_PASSWORD` và tạo tài khoản `admin@interntrack.local` nếu tài khoản đó chưa tồn tại.

Seed tài khoản mẫu (tùy chọn, chỉ dùng database development/test):

```powershell
python -m app.db.seed_sample_data
```

Lệnh này cần `SAMPLE_USER_PASSWORD`; trong development, nó cũng đảm bảo tài khoản ADMIN mặc định đã tồn tại. Seed kỳ thực tập, tiêu chí đánh giá và phân nhóm mẫu (tùy chọn):

```powershell
python -m app.db.seed
```

Chỉ chạy seed mẫu trên database dùng thử; lệnh cuối tạo dữ liệu mẫu và có thể gán các sinh viên hiện có vào nhóm.

## 4. Chạy backend

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- Swagger/OpenAPI: <http://127.0.0.1:8000/docs>
- OpenAPI JSON: <http://127.0.0.1:8000/openapi.json>
- Health check: <http://127.0.0.1:8000/health>
- Kết nối database: <http://127.0.0.1:8000/test-connection>

## 5. Chạy frontend

Mở terminal thứ hai tại thư mục dự án:

```powershell
python -m http.server 5500 --bind 127.0.0.1 --directory frontend
```

Mở <http://127.0.0.1:5500/home.html>. Đăng nhập bằng tài khoản ADMIN development đã seed để vào [admin.html](./frontend/admin.html); [users.html](./frontend/users.html) chuyển tới màn quản lý user trong dashboard ADMIN hiện có. Không mở HTML trực tiếp bằng `file://` vì ứng dụng dùng JavaScript ES modules và cần gọi API.

Frontend hiện cấu hình API tại `http://localhost:8000/api/v1`. Nếu đổi địa chỉ backend, cập nhật thẻ `meta[name="api-base-url"]` trong các trang frontend tương ứng. Khi đổi port/origin frontend, cập nhật danh sách CORS trong `app/main.py`.

## 6. Chạy kiểm thử

```powershell
python -m pip install -r requirements-test.txt
python -m unittest discover -s tests -v
```

Test dùng SQLite trong bộ nhớ; chúng không thay thế việc kiểm tra cấu hình MySQL hoặc chạy migration trên database thực.