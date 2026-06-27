# Sahal Water Delivery WebView

Flutter WebView wrapper for the local PHP/XAMPP project.

## Run with Android emulator

Start XAMPP Apache and MySQL, then run:

```bash
flutter run
```

The default URL is:

```text
http://10.0.2.2/biyo-system/
```

`10.0.2.2` means your computer localhost from the Android emulator.

## Run with a real Android phone

Phone and computer must be on the same WiFi.

Find your computer IPv4 address:

```powershell
ipconfig
```

Then run, replacing the IP:

```bash
flutter run --dart-define=BIYO_BASE_URL=http://192.168.1.20/biyo-system/
```

## Required local services

- XAMPP Apache running
- XAMPP MySQL running
- `http://localhost/biyo-system/` working in the computer browser

A new Flutter project.
