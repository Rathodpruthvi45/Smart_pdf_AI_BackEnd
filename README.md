# FastAPI Authentication API

This is a secure, production-ready authentication API built with FastAPI, SQLAlchemy, and OAuth2 with JWT tokens.

## Features

- User registration with email verification
- Secure login with JWT tokens stored in HTTP-only cookies
- Refresh token mechanism
- Password reset functionality
- Role-based access control (RBAC)
- Rate limiting to prevent brute force attacks
- CSRF protection
- Secure headers
- Database migrations with Alembic

## Requirements

- Python 3.8+
- MySQL 5.7+
- Redis 6.0+

## Installation

1. Clone the repository
2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Create a MySQL database:
   ```sql
   CREATE DATABASE auth_db;
   ```
5. Copy `.env.example` to `.env` and update the environment variables
6. Run database migrations:
   ```bash
   alembic upgrade head
   ```
7. Start the server:
   ```bash
   uvicorn app.main:app --reload
   ```

## Environment Variables

- `DATABASE_URL`: MySQL connection string
- `SECRET_KEY`: Secret key for JWT tokens
- `ALGORITHM`: JWT algorithm (default: HS256)
- `ACCESS_TOKEN_EXPIRE_MINUTES`: Access token expiration time in minutes
- `REFRESH_TOKEN_EXPIRE_DAYS`: Refresh token expiration time in days
- `CORS_ORIGINS`: Comma-separated list of allowed origins for CORS
- `REDIS_HOST`: Redis host
- `REDIS_PORT`: Redis port
- `SMTP_HOST`: SMTP host for sending emails
- `SMTP_PORT`: SMTP port
- `SMTP_USER`: SMTP username
- `SMTP_PASSWORD`: SMTP password
- `EMAIL_FROM`: Email address to send emails from
- `CSRF_SECRET`: Secret key for CSRF protection

## API Documentation

Once the server is running, you can access the API documentation at:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API Endpoints

### Authentication

- `POST /api/v1/auth/register`: Register a new user
- `POST /api/v1/auth/login`: Login with username and password
- `POST /api/v1/auth/login/json`: Login with JSON payload
- `POST /api/v1/auth/refresh`: Refresh access token
- `POST /api/v1/auth/logout`: Logout
- `POST /api/v1/auth/verify-email`: Verify email
- `POST /api/v1/auth/request-password-reset`: Request password reset
- `POST /api/v1/auth/reset-password`: Reset password

### Users

- `GET /api/v1/users/me`: Get current user
- `PUT /api/v1/users/me`: Update current user
- `POST /api/v1/users/me/change-password`: Change current user's password
- `GET /api/v1/users`: Get all users (admin only)
- `GET /api/v1/users/{user_id}`: Get user by ID (admin and moderator only)
- `PUT /api/v1/users/{user_id}/role`: Update user role (admin only)

### Protected Routes

- `GET /api/v1/protected/public`: Public route
- `GET /api/v1/protected/authenticated`: Authenticated route
- `GET /api/v1/protected/verified`: Verified route
- `GET /api/v1/protected/user`: User route
- `GET /api/v1/protected/moderator`: Moderator route
- `GET /api/v1/protected/admin`: Admin route

## Security

This API implements several security measures:

- Passwords are hashed using bcrypt
- JWT tokens are stored in HTTP-only, secure cookies
- CSRF protection with double submit cookie pattern
- Rate limiting to prevent brute force attacks
- Secure headers to prevent common web vulnerabilities
- Role-based access control
- Email verification
- Refresh token rotation

## License

MIT
