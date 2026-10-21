# 🚀 Autorun Scripts Guide - AI Nurse Health Kiosk

## 📋 Available Scripts

Kami menyediakan 3 script untuk memudahkan Anda menjalankan server:

### 1. **quick_start.bat** ⚡ (Recommended)
Script paling simple untuk quick launch!

**Cara Pakai:**
- Double click `quick_start.bat`
- Server langsung jalan di port 8001
- Browser otomatis terbuka

**Kelebihan:**
- ✅ Cepat dan simple
- ✅ No questions asked
- ✅ Auto open browser

---

### 2. **autorun.bat** 🎯 (Standard)
Script dengan informasi lengkap dan auto-migration.

**Cara Pakai:**
- Double click `autorun.bat`
- Tunggu proses:
  1. Aktivasi virtual environment
  2. Check dan run migrations
  3. Start server di port 8001
  4. Browser otomatis terbuka setelah 3 detik

**Kelebihan:**
- ✅ Auto migration check
- ✅ Detailed progress info
- ✅ Error handling
- ✅ Colorful console output

---

### 3. **autorun_advanced.bat** 🛠️ (Power Users)
Script dengan menu lengkap untuk berbagai operasi.

**Cara Pakai:**
- Double click `autorun_advanced.bat`
- Pilih opsi dari menu:

```
[1] Start Server (Port 8001)           - Jalankan server biasa
[2] Start Server + Open Browser        - Jalankan + buka browser
[3] Start Server (Custom Port)         - Pakai port custom
[4] Run Migrations Only                - Hanya jalankan migrasi
[5] Create Superuser                   - Buat admin baru
[6] Collect Static Files               - Kumpulkan static files
[7] Install/Update Requirements        - Install/update packages
[8] Check System Status                - Cek status sistem
[9] Exit                               - Keluar
```

**Kelebihan:**
- ✅ Full control
- ✅ Multiple operations
- ✅ System diagnostics
- ✅ Easy maintenance

---

## 🎯 Quick Comparison

| Feature                  | quick_start.bat | autorun.bat | autorun_advanced.bat |
|-------------------------|-----------------|-------------|----------------------|
| Speed                   | ⚡⚡⚡           | ⚡⚡          | ⚡                    |
| Auto Migration          | ❌              | ✅           | ✅ (Manual)           |
| Auto Browser            | ✅              | ✅           | ✅ (Optional)         |
| Error Messages          | ❌              | ✅           | ✅                    |
| Custom Port             | ❌              | ❌           | ✅                    |
| Management Tools        | ❌              | ❌           | ✅                    |
| Best For                | Daily use       | First time  | Development          |

---

## 📝 Recommended Usage

### Untuk Pengguna Harian:
```
quick_start.bat
```
Paling cepat, langsung jalan!

### Untuk Pertama Kali / Setelah Update:
```
autorun.bat
```
Memastikan database terupdate dengan migration.

### Untuk Developer / Maintenance:
```
autorun_advanced.bat
```
Lengkap dengan tools maintenance.

---

## 🔧 Troubleshooting

### Error: "Virtual environment not found"
**Solusi:**
1. Buka Command Prompt di folder `monolith`
2. Jalankan:
   ```bash
   python -m venv venv
   pip install -r requirements.txt
   ```
3. Coba jalankan script lagi

### Error: "Port 8001 is already in use"
**Solusi:**
1. Tutup server yang sedang berjalan (Ctrl+C)
2. Atau gunakan `autorun_advanced.bat` → Option [3] untuk pakai port lain
3. Atau stop process yang pakai port 8001:
   ```bash
   netstat -ano | findstr :8001
   taskkill /PID <PID_NUMBER> /F
   ```

### Browser tidak otomatis terbuka
**Solusi:**
- Buka manual di browser: http://127.0.0.1:8001
- Check firewall/antivirus settings

### Error: "Module not found"
**Solusi:**
1. Gunakan `autorun_advanced.bat`
2. Pilih option [7] - Install/Update Requirements
3. Atau manual:
   ```bash
   cd monolith
   venv\Scripts\activate
   pip install -r requirements.txt
   ```

---

## 🌐 Default URLs

Setelah server berjalan, akses melalui:

- **Kiosk Home:** http://127.0.0.1:8001
- **Dashboard:** http://127.0.0.1:8001/dashboard
- **Patient List:** http://127.0.0.1:8001/patients
- **QR Scanner:** http://127.0.0.1:8001/qr-scanner
- **Admin Panel:** http://127.0.0.1:8001/admin

---

## ⚙️ Advanced: Custom Port Permanently

Jika ingin selalu pakai port selain 8001:

1. Edit file `.bat` yang Anda gunakan
2. Cari baris: `python manage.py runserver 0.0.0.0:8001`
3. Ganti `8001` dengan port yang Anda inginkan
4. Save dan jalankan

**Contoh:**
```batch
python manage.py runserver 0.0.0.0:8080
```

---

## 💡 Tips & Tricks

### 1. Buat Shortcut di Desktop
- Right-click pada `quick_start.bat`
- Pilih "Create shortcut"
- Drag shortcut ke Desktop
- Rename sesuai keinginan (misal: "🏥 AI Nurse")

### 2. Pin to Taskbar
- Buat shortcut seperti di atas
- Right-click shortcut → Pin to taskbar

### 3. Run as Administrator (jika perlu)
- Right-click file `.bat`
- Pilih "Run as administrator"
- Berguna jika ada permission issues

### 4. Custom Icon
- Right-click shortcut
- Properties → Change Icon
- Pilih icon yang Anda suka

### 5. Silent Mode (No Console Window)
Buat file `.vbs` dengan isi:
```vbscript
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "C:\AI_Nurse\quick_start.bat", 0
Set WshShell = Nothing
```
Double-click file `.vbs` ini untuk run tanpa console window.

---

## 🆘 Need Help?

Jika masih ada masalah:

1. Check log di console window
2. Lihat error message
3. Cek `db.sqlite3` ada atau tidak
4. Pastikan Python terinstall
5. Pastikan virtual environment ada di `monolith/venv`

---

## 📱 Quick Reference Card

```
╔═══════════════════════════════════════════════╗
║         AI NURSE - QUICK REFERENCE           ║
╠═══════════════════════════════════════════════╣
║ START SERVER:                                 ║
║   → Double-click: quick_start.bat            ║
║                                               ║
║ ACCESS KIOSK:                                 ║
║   → http://127.0.0.1:8001                    ║
║                                               ║
║ STOP SERVER:                                  ║
║   → Press Ctrl+C in console window           ║
║                                               ║
║ ADMIN LOGIN:                                  ║
║   → http://127.0.0.1:8001/admin              ║
║                                               ║
║ TROUBLESHOOT:                                 ║
║   → Use: autorun_advanced.bat                ║
║   → Option [8] - Check System Status         ║
╚═══════════════════════════════════════════════╝
```

---

**Happy coding! 🚀💙**

Last Updated: December 2024