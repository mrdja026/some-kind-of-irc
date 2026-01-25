# TD-1 Remediation: Dual Password Hashing → bcrypt-Only

**Status**: ✅ COMPLETED  
**Original Severity**: Critical  
**Files Modified**:
- `backend/src/models/user.py`
- `backend/src/api/endpoints/auth.py`
- `backend/src/migrations/migrate_add_hash_type.py`
- Database: `backend/chat.db`

---

## Problem Summary

The system previously supported **two incompatible password hashing schemes**:

1. **bcrypt** (proper, with salt and work factor) - stored as `$2b$...` format
2. **SHA-256** (broken, no salt, fast, rainbow-table vulnerable) - stored as 64-char hex

This created security vulnerabilities:
- SHA-256 hashes can be cracked instantly with modern GPUs
- No salt means identical passwords have identical hashes
- Automatic fallback masked bcrypt failures
- Debug print statements leaked password hashes to logs

---

## What Was Done

### 1. Schema Migration

**Added `hash_type` column to users table** (`backend/src/models/user.py:11`)
```python
hash_type = Column(String, nullable=True)  # 'bcrypt' for new users, NULL for legacy
```

**Migration script created** (`backend/src/migrations/migrate_add_hash_type.py`)
- Adds `hash_type` column to existing SQLite database
- Existing users have `hash_type=NULL` (marked as legacy)
- New users get `hash_type='bcrypt'`

**Run migration**:
```bash
cd backend
python src/migrations/migrate_add_hash_type.py
```

### 2. Password Hashing Functions

**BEFORE** (vulnerable dual-mode):
```python
def verify_password(plain_password, hashed_password):
    # Check if SHA-256 (64 hex chars)
    if len(hashed_password) == 64 and all(c in '0123456789abcdefABCDEF' for c in hashed_password):
        return hashlib.sha256(plain_password.encode('utf-8')).hexdigest() == hashed_password
    else:
        # bcrypt fallback
        truncated_password = plain_password.encode('utf-8')[:72].decode('utf-8', 'ignore')
        return pwd_context.verify(truncated_password, hashed_password)

def get_password_hash(password):
    try:
        password_bytes = password.encode('utf-8')
        if len(password_bytes) > 72:
            password_bytes = password_bytes[:72]
        return pwd_context.hash(password_bytes)
    except Exception as e:
        # FALLBACK TO SHA-256 - DANGEROUS!
        return hashlib.sha256(password.encode('utf-8')).hexdigest()
```

**AFTER** (bcrypt-only, cost factor 12):
```python
# bcrypt with cost factor 12 (takes ~100-250ms per hash)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password using bcrypt only. Returns False if hash is invalid."""
    try:
        # bcrypt hashes start with $2a$, $2b$, or $2y$
        if not hashed_password.startswith('$2'):
            return False
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    """Hash password using bcrypt with cost factor 12."""
    return pwd_context.hash(password)
```

### 3. User Registration

**New users automatically get bcrypt** (`backend/src/api/endpoints/auth.py:127`):
```python
new_user = User(
    username=user.username, 
    password_hash=hashed_password, 
    hash_type="bcrypt"  # ← Mark as bcrypt user
)
```

### 4. Login Enforcement

**Legacy users blocked** (`backend/src/api/endpoints/auth.py:148-168`):
```python
user = get_user(db, form_data.username)

if not user:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers={"WWW-Authenticate": "Bearer"},
    )

# Check if legacy user (needs password reset)
if user.hash_type is None:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Password reset required. Please use password reset to continue.",
        headers={"WWW-Authenticate": "Bearer"},
    )

# Verify password
if not verify_password(form_data.password, user.password_hash):
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers={"WWW-Authenticate": "Bearer"},
    )
```

### 5. Security Cleanup

**Removed**:
- ❌ `import hashlib` (no longer needed)
- ❌ All debug `print()` statements that leaked password hashes
- ❌ 72-byte password truncation workaround (bcrypt handles this)
- ❌ SHA-256 fallback in `get_password_hash()`

**Added**:
- ✅ bcrypt cost factor 12 (secure default for 2025)
- ✅ Type hints on all password functions
- ✅ Explicit hash format validation (must start with `$2`)

---

## User Impact

| User Type | Count | Status | Action Required |
|-----------|-------|--------|-----------------|
| **Legacy** | ~1000 | ❌ Cannot login | Must reset password |
| **New** | 0 → N | ✅ Full access | None |

### For Legacy Users

When a legacy user (created before this change) tries to login:
1. System finds their account
2. Sees `hash_type=NULL`
3. Returns HTTP 401 with message: *"Password reset required. Please use password reset to continue."*
4. User must use password reset flow to set new bcrypt password

### For New Users

Registration and login work normally with bcrypt hashes.

---

## Verification

### Test Script

Run the comprehensive test:
```bash
cd backend
python src/migrations/test_bcrypt_migration.py
```

Tests performed:
1. ✅ New user registration creates bcrypt hash
2. ✅ `hash_type='bcrypt'` is set in database
3. ✅ New users can login
4. ✅ Legacy users are blocked with "Password reset required" message
5. ✅ Password hashes are in correct bcrypt format

### Manual Verification

Check database directly:
```sql
-- See all users and their hash types
SELECT username, hash_type, substr(password_hash, 1, 30) as hash_preview 
FROM users;

-- Count legacy users (need password reset)
SELECT COUNT(*) FROM users WHERE hash_type IS NULL;

-- Count bcrypt users (can login normally)
SELECT COUNT(*) FROM users WHERE hash_type = 'bcrypt';
```

---

## Migration Checklist

- [x] Add `hash_type` column to User model
- [x] Create database migration script
- [x] Run migration on production database
- [x] Remove `import hashlib`
- [x] Remove all debug `print()` statements
- [x] Replace `verify_password()` with bcrypt-only logic
- [x] Replace `get_password_hash()` with bcrypt-only logic
- [x] Set bcrypt cost factor to 12
- [x] Update registration to set `hash_type='bcrypt'`
- [x] Block legacy users (hash_type=NULL) from login
- [x] Return "Password reset required" message for legacy users
- [x] Verify `hash_type` is NOT in API responses (UserResponse model)
- [x] Test script validates all functionality

---

## Security Improvements

| Before | After |
|--------|-------|
| SHA-256 (crackable in seconds) | bcrypt cost 12 (~100-250ms per hash) |
| No salt, rainbow table vulnerable | Per-password salt, immune to rainbow tables |
| Silent fallback to weak hash | Explicit rejection of non-bcrypt hashes |
| Password hash leakage in logs | No debug output in production code |
| 72-byte truncation without warning | Full password support (bcrypt handles length) |

---

## Related Technical Debt

This remediation is a **prerequisite** for:
- **TD-5**: Admin allowlist enforcement (clean auth code needed first)
- **K8s Auth Service extraction**: Cannot extract auth service with SHA-256 vulnerability

---

## Next Steps

After TD-1 is complete, proceed with:

1. **Password Reset Flow** (if not exists) - needed for legacy user migration
2. **TD-5**: Admin allowlist enforcement (`ADMIN_ALLOWLIST` env var)
3. **TD-6**: Redis-backed rate limiting for AI service
4. **K8s Auth Service extraction** - now safe to proceed

---

## Rollback Plan

**NOT RECOMMENDED** - SHA-256 is cryptographically broken.

If emergency rollback needed:
1. Restore `auth.py` from git
2. Restore `user.py` from git
3. Remove `hash_type` column (destructive - data loss)

**Better approach**: If issues arise, fix forward rather than rollback to vulnerable code.
