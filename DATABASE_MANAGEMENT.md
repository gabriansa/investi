# Database Management Scripts

Quick reference for managing your PostgreSQL database on the Raspberry Pi.

## Scripts Overview

All scripts are located in the `scripts/` directory.

### 1. Pull Production Logs
```bash
./scripts/pull-prod.sh
```
Downloads all log files from the Raspberry Pi to `prod-data/logs/`:
- `bot-output.log` - Main application logs
- `bot-errors.log` - Error logs  
- `investi-update.log` - Update logs

**Note:** Does NOT pull the database. Use direct PostgreSQL access for database queries.

### 2. Backup Database
```bash
./scripts/backup-db.sh
```
Creates a timestamped backup of the PostgreSQL database from the Pi.
- Backups saved to: `backups/investi_backup_YYYYMMDD_HHMMSS.sql`
- Automatically offers to clean up backups older than 30 days

### 3. Restore Database
```bash
./scripts/restore-db.sh <backup_file>
```
Restores a database backup to the Raspberry Pi.

Examples:
```bash
# Restore using filename
./scripts/restore-db.sh investi_backup_20241210_143022.sql

# Restore using full path
./scripts/restore-db.sh /path/to/backup.sql

# List available backups
./scripts/restore-db.sh
```

### 4. Delete Database
```bash
./scripts/delete-db.sh
```
**DANGER ZONE:** Deletes the database completely.
- Prompts for confirmation for local database
- Prompts for confirmation for remote (Pi) database
- Drops and recreates an empty database

## Accessing the Database

### From Your Mac - SSH Tunnel (Recommended)

```bash
# Open SSH tunnel (in one terminal)
ssh -L 5432:localhost:5432 gabrigoo@100.120.218.103

# Connect to database (in another terminal)
psql -h localhost investi
```

**Using a GUI tool:**
- **Postico** (Mac): https://eggerapps.at/postico/
- **pgAdmin** (Cross-platform): https://www.pgadmin.org/
- **DBeaver** (Cross-platform): https://dbeaver.io/

Configure SSH tunnel in your GUI tool:
- SSH Host: `100.120.218.103`
- SSH User: `gabrigoo`
- Database Host: `localhost` (important!)
- Database Port: `5432`
- Database: `investi`
- User: `gabrigoo` (or leave blank to use your system user)

### From Your Mac - Direct Connection (Optional)

If you've configured remote access in PostgreSQL (see `RASPBERRY_PI_POSTGRES_SETUP.md`):

```bash
psql -h 100.120.218.103 investi
```

### From Raspberry Pi

SSH into the Pi first:
```bash
ssh gabrigoo@100.120.218.103
```

Then connect to database:
```bash
psql investi
```

Useful psql commands:
```sql
\dt              -- List all tables
\d table_name    -- Describe a table's structure
\l               -- List all databases
\du              -- List all users
\q               -- Quit psql

-- Query examples
SELECT * FROM users;
SELECT * FROM positions WHERE is_active = true;
```

## PostgreSQL Service Management (on Pi)

```bash
# Check if PostgreSQL is running
sudo systemctl status postgresql

# Start PostgreSQL
sudo systemctl start postgresql

# Stop PostgreSQL
sudo systemctl stop postgresql

# Restart PostgreSQL
sudo systemctl restart postgresql

# View PostgreSQL logs
sudo journalctl -u postgresql -n 50
```

PostgreSQL automatically starts on boot - no configuration needed!

## Common Tasks

### Create a Manual Backup Before Updates
```bash
./scripts/backup-db.sh
```

### Pull Logs to Check for Issues
```bash
./scripts/pull-prod.sh
cat prod-data/logs/bot-errors.log
```

### Reset Database to Fresh State
```bash
# Backup first (optional but recommended)
./scripts/backup-db.sh

# Delete and recreate
./scripts/delete-db.sh
```

### Restore from Backup
```bash
# List available backups
ls -lh backups/

# Restore specific backup
./scripts/restore-db.sh investi_backup_20241210_143022.sql
```

## Directory Structure

```
investi/
├── scripts/
│   ├── pull-prod.sh       # Pull logs from Pi
│   ├── backup-db.sh       # Backup PostgreSQL database
│   ├── restore-db.sh      # Restore PostgreSQL database
│   ├── delete-db.sh       # Delete/reset database
│   └── clean-logs.sh      # Clean local logs
├── backups/               # Database backups (created by backup-db.sh)
│   └── investi_backup_*.sql
├── prod-data/             # Downloaded production data (created by pull-prod.sh)
│   └── logs/
│       ├── bot-output.log
│       ├── bot-errors.log
│       └── investi-update.log
└── logs/                  # Local development logs
    ├── bot-output.log
    └── bot-errors.log
```

## Troubleshooting

### Can't Connect to Database from Mac via SSH Tunnel

1. Make sure SSH tunnel is running in another terminal
2. Connect to `localhost` (not the Pi's IP) when using tunnel
3. Verify PostgreSQL is running on Pi: `sudo systemctl status postgresql`

### Can't Connect via Direct Connection

1. Make sure you've enabled remote access (see `RASPBERRY_PI_POSTGRES_SETUP.md`)
2. Check Pi's firewall isn't blocking port 5432
3. Verify PostgreSQL is listening: `ssh gabrigoo@100.120.218.103 "sudo netstat -plnt | grep 5432"`

### Backup/Restore Fails

1. Check SSH connection: `ssh gabrigoo@100.120.218.103`
2. Verify PostgreSQL is running on Pi: `sudo systemctl status postgresql`
3. Make sure the database exists: `ssh gabrigoo@100.120.218.103 "psql -l"`

### Database Performance Issues

For Raspberry Pi, you can optimize PostgreSQL settings. See the "Performance Notes" section in `RASPBERRY_PI_POSTGRES_SETUP.md`.

## Security Notes

- Keep database backups secure (they contain sensitive data)
- SSH tunnel is more secure than direct connections
- Your Pi's SSH password protects database access
- Only enable direct remote access if needed (SSH tunnel is usually better)

## Automated Backups (Optional)

To set up daily automated backups on the Pi:

```bash
# On the Raspberry Pi
crontab -e

# Add this line for daily backup at 3 AM:
0 3 * * * cd ~/investi && mkdir -p backups && pg_dump investi > ~/investi/backups/investi_backup_$(date +\%Y\%m\%d).sql
```

Clean up old backups monthly:
```bash
# Add this line to delete backups older than 30 days (runs monthly on 1st at 4 AM):
0 4 1 * * find ~/investi/backups -name "investi_backup_*.sql" -mtime +30 -delete
```
