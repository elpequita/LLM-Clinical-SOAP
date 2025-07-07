#!/bin/bash
# MySQL Database Verification Commands
# Save this as verify_mysql.sh and run: bash verify_mysql.sh

echo "🏥 Clinical Documentation AI - MySQL Verification"
echo "=================================================="

# Database connection details
DB_HOST="localhost"
DB_USER="clinical_user"
DB_PASS="clinical_password"
DB_NAME="clinical_docs"

echo "📊 Checking database connection..."
mysql -h$DB_HOST -u$DB_USER -p$DB_PASS -e "SELECT 'Connection successful' as status;"

echo ""
echo "📋 Showing all tables..."
mysql -h$DB_HOST -u$DB_USER -p$DB_PASS $DB_NAME -e "SHOW TABLES;"

echo ""
echo "👥 Showing users table structure..."
mysql -h$DB_HOST -u$DB_USER -p$DB_PASS $DB_NAME -e "DESCRIBE users;"

echo ""
echo "📝 Showing transcriptions table structure..."
mysql -h$DB_HOST -u$DB_USER -p$DB_PASS $DB_NAME -e "DESCRIBE transcriptions;"

echo ""
echo "⚙️ Showing app_settings table structure..."
mysql -h$DB_HOST -u$DB_USER -p$DB_PASS $DB_NAME -e "DESCRIBE app_settings;"

echo ""
echo "📊 Database statistics..."
mysql -h$DB_HOST -u$DB_USER -p$DB_PASS $DB_NAME -e "
SELECT 'Users' as table_name, COUNT(*) as count FROM users
UNION ALL
SELECT 'Transcriptions' as table_name, COUNT(*) as count FROM transcriptions
UNION ALL
SELECT 'Settings' as table_name, COUNT(*) as count FROM app_settings;
"

echo ""
echo "👤 Recent users..."
mysql -h$DB_HOST -u$DB_USER -p$DB_PASS $DB_NAME -e "
SELECT id, username, created_at, is_active 
FROM users 
ORDER BY created_at DESC 
LIMIT 5;
"

echo ""
echo "📝 Recent transcriptions..."
mysql -h$DB_HOST -u$DB_USER -p$DB_PASS $DB_NAME -e "
SELECT t.id, t.filename, LEFT(t.transcription_text, 50) as text_preview, 
       t.language, t.status, t.created_at, u.username
FROM transcriptions t
JOIN users u ON t.user_id = u.id
ORDER BY t.created_at DESC 
LIMIT 5;
"

echo ""
echo "⚙️ App settings..."
mysql -h$DB_HOST -u$DB_USER -p$DB_PASS $DB_NAME -e "
SELECT setting_key, setting_value, updated_at 
FROM app_settings;
"

echo ""
echo "✅ Verification complete!"