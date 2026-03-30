# Futball

Futball adalah web analisis sepak bola dan livescore berbasis Django. Aplikasi ini menggabungkan halaman publik untuk melihat klasemen, statistik, xG, berita, fixture, hasil pertandingan, dan profil pemain, dengan panel admin internal untuk input dan pengelolaan data pertandingan.

Project ini juga punya alur import data StatsBomb dan simulasi replay pertandingan, sehingga bisa dipakai sebagai fondasi dashboard analitik sepak bola sekaligus experience livescore sederhana.

## Fitur Utama

- Livescore dan tracker pertandingan harian di halaman home.
- Fixture, hasil pertandingan, dan halaman detail match.
- Klasemen liga berbasis hasil pertandingan yang tersimpan.
- Dashboard analisis musim: total gol, rata-rata gol, top attack, best defence, dan ringkasan xG.
- Visualisasi `xG` per tim dan `xG pitch map`.
- Profil pemain dan statistik performa per pertandingan.
- Halaman berita sepak bola.
- Admin panel internal untuk CRUD tim, stadion, pemain, kompetisi, musim, match, shot, dan match stats.
- Pipeline import data StatsBomb untuk competitions, matches, lineups, events, dan substitutions.
- Replay event pertandingan untuk simulasi flow live match.

## Posisi Aplikasi

Futball dibangun sebagai dua experience utama:

1. `Web analysis`
   Menyediakan statistik liga, xG, player metrics, match insights, dan ringkasan performa musim.

2. `Livescore`
   Menyediakan tracker pertandingan, hasil terbaru, fixture mendatang, detail pertandingan, serta simulasi replay event melalui `MatchState`.

## Arsitektur Singkat

- `config/`: konfigurasi project Django, settings, root URL.
- `core/`: public site, domain models, public views, news, standings, fixtures, players, stats.
- `analytics/`: service layer untuk standings, xG, player metrics, passing, dan event processing.
- `admin/`: admin panel internal untuk data entry dan manajemen data pertandingan.
- `templates/` dan `static/`: UI public site dan admin panel.
- `docs/app-diagram.md`: diagram arsitektur aplikasi.

Lihat diagram detail di [docs/app-diagram.md](docs/app-diagram.md).

## Teknologi

- Python
- Django
- Django REST Framework
- MySQL
- Pillow
- Jazzmin

## Struktur Data Inti

Beberapa entitas utama yang dipakai:

- `Competition` dan `Season`
- `Team` dan `Stadium`
- `Player` dan `PlayerMatch`
- `Match`, `MatchTeamStats`, dan `MatchState`
- `Event`, `Shot`, `Pass`, dan `Substitution`
- `News`

## Halaman Utama

- `/` : home, tracker pertandingan, highlight, berita, result, fixture.
- `/klasemen/` : klasemen liga.
- `/stats/` : dashboard analitik musim.
- `/xg-pitch/` : visualisasi shot map dan xG pitch map.
- `/fixtures/` : daftar pertandingan dan hasil.
- `/fixtures/<match_id>/` : detail pertandingan.
- `/players/` : daftar pemain.
- `/players/<player_id>/` : profil pemain.
- `/players/<player_id>/stats/` : statistik detail pemain.
- `/news/` : daftar berita.
- `/admin/` : panel admin internal.

## Setup Lokal

### 1. Buat virtual environment

```bash
python -m venv env
source env/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Siapkan database MySQL

Buat database dengan nama `futball`, lalu sesuaikan kredensial di [config/settings.py](/home/dani/Documents/Wavegame/new/futball/config/settings.py) bila diperlukan.

Default saat ini:

- `NAME = futball`
- `USER = root`
- `PASSWORD = root`
- `HOST = localhost`
- `PORT = 3306`

### 4. Jalankan migrasi

```bash
python manage.py makemigrations
python manage.py migrate
```

### 5. Buat akun admin

```bash
python manage.py createsuperuser
```

### 6. Jalankan server

```bash
python manage.py runserver
```

## Import Data StatsBomb

Project ini sudah menyiapkan command untuk ingest data StatsBomb ke database lokal.

Struktur default mengarah ke:

- `data/statsbomb/competitions.json`
- `data/statsbomb/matches/`
- `data/statsbomb/events/`
- `data/statsbomb/lineups/`

Jalankan pipeline penuh:

```bash
python manage.py run_statsbomb_pipeline
```

Atau jalankan step tertentu:

```bash
python manage.py import_competitions --path data/statsbomb/competitions.json
python manage.py import_matches --base-dir data/statsbomb/matches
python manage.py import_lineups --lineups-dir data/statsbomb/lineups
python manage.py import_events data/statsbomb/events
python manage.py import_substitution --events-dir data/statsbomb/events
```

## Replay Livescore

Untuk simulasi flow pertandingan seperti livescore berbasis event:

```bash
python manage.py replay_match <match_id> --speed 0.2
```

Command ini akan memproses event secara berurutan dan meng-update `MatchState` memakai `analytics.services.event_processor`.

## Alur Analitik

Lapisan `analytics/services` menangani agregasi data untuk:

- klasemen liga
- season summary
- xG table
- player profile stats
- recent player match stats
- passing analytics
- event processing untuk live state

Dengan pola ini, halaman web tetap tipis di layer view dan logika agregasi dipusatkan di service.

## Admin Panel

Panel admin internal dipakai untuk manajemen data inti:

- team
- stadium
- player
- competition
- season
- match
- match team stats
- shot

Panel ini dibatasi oleh `is_staff` dan menggunakan login yang mengarahkan user staff ke dashboard admin, sementara user biasa diarahkan ke home.

## Use Case Cocok

Project ini cocok dipakai untuk:

- website analisis sepak bola internal kampus atau komunitas
- portal statistik pertandingan
- eksperimen visualisasi xG dan event data
- prototype livescore berbasis event replay
- dashboard data hasil ingest dari StatsBomb

## Catatan

- File media dan static disajikan dari konfigurasi lokal saat `DEBUG=True`.
- Importer StatsBomb mengasumsikan data source tersedia di folder lokal.
- Beberapa fitur livescore saat ini bersifat replay/simulasi, belum push real-time via websocket.

## Pengembangan Lanjutan

Beberapa arah pengembangan yang natural:

- tambah API publik untuk mobile app atau frontend terpisah
- realtime update via WebSocket atau Django Channels
- filter statistik yang lebih kaya per kompetisi, musim, tim, dan pemain
- heatmap passing, shot zones, dan event timeline interaktif
- CI/CD dan test coverage yang lebih lengkap

## Lisensi

Belum ditentukan.

