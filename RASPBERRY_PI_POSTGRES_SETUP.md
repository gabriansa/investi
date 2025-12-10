# PostgreSQL Setup on Raspberry Pi

Simple setup guide - just like the Mac setup!

## Step 1: Install PostgreSQL

SSH into your Raspberry Pi:

```bash
ssh gabrigoo@100.120.218.103
```

Install PostgreSQL:

```bash
sudo apt update
sudo apt install postgresql postgresql-contrib -y
```

## Step 2: Create the Database

Switch to the postgres user and create the database:

```bash
sudo -u postgres createdb investi
```

That's it! PostgreSQL is installed and your database is ready.

## Step 3: Update Your .env File

On the Raspberry Pi, in your investi directory:

```bash
cd ~/investi
nano .env
```

Add this line (no password needed for local connections):

```
DATABASE_URL=postgresql:///investi
```

Save and exit (Ctrl+X, Y, Enter).

## Step 4: Install Python Driver

```bash
cd ~/investi
source .venv/bin/activate
pip install asyncpg
```

## Done! ✅

PostgreSQL will:
- ✅ Auto-start on boot (managed by systemd)
- ✅ Run in the background always
- ✅ Use "peer authentication" (no password needed for local connections)

Your bot runs on the same machine, so it connects locally without needing a password. Someone would need:
1. SSH access to your Pi (your Pi password)
2. To be logged in as your user
3. Then they could access the database

So yes, your Pi's SSH security is the main protection layer!

## Verify It's Working

Check PostgreSQL is running:

```bash
sudo systemctl status postgresql
```

Test database connection:

```bash
psql investi
```

You should connect directly! Type `\q` to exit.

## Managing PostgreSQL

```bash
# Check status
sudo systemctl status postgresql

# Restart if needed
sudo systemctl restart postgresql

# View logs if something goes wrong
sudo journalctl -u postgresql -n 50
```

## Accessing from Your Mac (Optional)

If you want to access the database from your Mac, you have two simple options:

### Option 1: SSH Tunnel (Recommended - Secure)

```bash
# Create SSH tunnel
ssh -L 5432:localhost:5432 gabrigoo@100.120.218.103

# In another terminal on your Mac
psql -h localhost investi
```

### Option 2: Direct Connection (if you configure remote access)

If you want direct access without SSH tunnel, edit PostgreSQL config on the Pi:

```bash
sudo nano /etc/postgresql/15/main/postgresql.conf
# Change: listen_addresses = '*'

sudo nano /etc/postgresql/15/main/pg_hba.conf  
# Add: host all all 100.0.0.0/8 trust

sudo systemctl restart postgresql
```

Then from Mac:
```bash
psql -h 100.120.218.103 investi
```

**Note:** This is less secure but fine for a home network on Tailscale.

## That's It!

Much simpler than the original guide. No users, no passwords, just works! 🎉
