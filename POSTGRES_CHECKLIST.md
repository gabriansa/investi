# Raspberry Pi PostgreSQL Setup Checklist

Super simple setup - just like on Mac!

## Installation (5 minutes)

### 1. SSH into Pi
```bash
ssh gabrigoo@100.120.218.103
```

### 2. Install PostgreSQL
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib -y
```

### 3. Create Database
```bash
sudo -u postgres createdb investi
```

### 4. Update .env
```bash
cd ~/investi
nano .env
```

Add this line:
```
DATABASE_URL=postgresql:///investi
```

Save: Ctrl+X, Y, Enter

### 5. Install Python Driver
```bash
cd ~/investi
source .venv/bin/activate
pip install asyncpg
```

### 6. Test It
```bash
psql investi
# Should connect! Type \q to exit
```

## ✅ Done!

PostgreSQL:
- Starts automatically on boot
- No password needed (you're already authenticated via SSH/system user)
- Ready for your bot to use

## Quick Commands

```bash
# Check status
sudo systemctl status postgresql

# Restart
sudo systemctl restart postgresql

# Access database
psql investi

# View logs
sudo journalctl -u postgresql -n 50
```

## Access from Mac (Optional)

**Easy way - SSH tunnel:**
```bash
ssh -L 5432:localhost:5432 gabrigoo@100.120.218.103
# Then in another terminal: psql -h localhost investi
```

**Or use GUI tool** (Postico, pgAdmin, DBeaver) with SSH tunnel configured.

See full details in [RASPBERRY_PI_POSTGRES_SETUP.md](RASPBERRY_PI_POSTGRES_SETUP.md)
