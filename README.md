# call_summary

Spec 01 добавляет PostgreSQL, приватное S3-хранилище MinIO, миграции 19 таблиц
и точки запуска API/worker. `/audio`, обработка очереди и чтение расшифровок
появятся в следующих specs. Worker сейчас только проверяет зависимости и ждёт
остановки, не захватывая задания.

## Локальный запуск

Нужны Docker Engine и Compose. Из корня проекта:

```bash
cp .env.example .env
# Замените локальные пароли; пароли в DSN должны совпадать с DB_*_PASSWORD.
make up
curl --fail http://localhost:8010/health
curl --fail http://localhost:8010/ready/read
curl --fail http://localhost:8010/ready/upload
make logs
```

`make up` собирает CPU-образ Python 3.14.6, запускает db/minio, применяет Alembic,
создаёт локальный workspace, приватный bucket и пользователя S3, затем API/worker.
Порты привязаны к localhost. Пароли в URL требуют percent encoding, если содержат
спецсимволы. Это локальное окружение: аутентификация и членство workspace ещё не
реализованы. `.env` не копируется в образ и не отслеживается Git.

Повторные команды безопасны:

```bash
make migrate
make storage-init
make bootstrap
make down            # контейнеры удалены, данные сохранены
make up              # те же volumes
```

Только явная `make destroy-volumes` удаляет данные PostgreSQL и MinIO.
Не используйте её для обычной остановки. Инициализация DB-ролей выполняется
только на пустом volume; изменение пароля в `.env` не меняет пароль существующей
роли. Для ротации используйте административное соединение и обновите DSN.

Закреплены PostgreSQL `17.6-bookworm`, MinIO `RELEASE.2025-09-07T16-13-09Z`,
mc `RELEASE.2025-08-13T08-35-41Z`; точные digest находятся в `compose.yaml`.
Доступность этих образов проверяется pull и фактическим запуском, а не наличием
тега в документации. [Исходный Docker guide MinIO](https://github.com/minio/minio/blob/master/docs/docker/README.md)
описывает команду `server /data`. Версию PostgreSQL для Supabase надо сверить
с целевым проектом на этапе переноса.

## Конфигурация и права

Внутри контейнеров: PostgreSQL `db:5432`, S3 `http://minio:9000`.
С хоста: `localhost:5432` и `http://localhost:9000`; порты меняются через `.env`.
Консоль MinIO: `http://localhost:9001`. При запуске Python с хоста замените
hostname в `DATABASE_URL`, `MIGRATION_DATABASE_URL` и `S3_ENDPOINT_URL`.

- `call_summary_migrator` владеет схемой `call_summary`; Alembic использует только
  `MIGRATION_DATABASE_URL`. История — `call_summary.alembic_version`.
- `call_summary_app` имеет USAGE схемы, SELECT/INSERT/UPDATE/DELETE таблиц и
  USAGE/SELECT identity-последовательностей. Нет DDL, superuser или доступа
  к записи Alembic. API/worker не получают административные пароли и DSN миграций.
- MinIO admin используется только для инициализации. Пользователь приложения
  может list/head bucket и put/get/head/delete объектов своего bucket; анонимное
  чтение и административные операции запрещены.
- На внешнем PostgreSQL заранее создайте эти login-роли и схему, принадлежащую
  migrator. Не выполняйте локальный init-скрипт над системными ролями Supabase.
- Пул каждого процесса ограничен `DB_POOL_SIZE` и `DB_MAX_OVERFLOW`.
  `/ready/read` проверяет таблицу БД, `/ready/upload` дополнительно проверяет bucket.
  Готовность инфраструктуры не означает, что `/audio` уже реализован.

S3-адаптер использует SigV4/path, синхронные вызовы выполняются в sync endpoints
FastAPI (thread pool) или worker. Есть put/get/head/delete/list с cursor и
скачивание во временный файл с независимой проверкой SHA-256 и очисткой.
Оба приложения используют сеть; `minio_data` монтируется только в MinIO.

## Миграции и модель

ORM/Core: `src/call_summary/db/models.py`. Ревизия `0001` использует зафиксированные
SQL-снимки рядом с ней; она не импортирует текущие модели. Это часть единой
истории Alembic, не отдельный способ применять схему. Новые изменения — новой
ревизией. UUID публичны, identity BIGINT используются для всех связей.

Составные FK проверяют workspace. DB triggers дополнительно проверяют связи
звонка, сеанса, дорожки, фрагмента, спикера и источников задач, включая UPDATE.
Ключи принадлежности существующих сущностей (workspace, meeting, stream, chunk
и соответствующие родители) неизменяемы: перенос выполняется созданием новой
сущности, а не UPDATE родителя. Это сохраняет корректность зависимых записей и
при конкурентных изменениях. Подтверждение человека и сопоставление спикера
остаются редактируемыми. Событие интеграции можно связать с сеансом один раз.
Допустимые статусы и виды заданий явно определены CHECK в модели/миграции.

## Проверки

```bash
uv sync --locked
# Значения для хоста берутся из вашей .env, с localhost вместо db/minio.
export TEST_DATABASE_URL="$DATABASE_URL"
export TEST_S3=1
make test-infra
```

Тесты требуют реальный мигрированный PostgreSQL под ролью приложения и MinIO.
Для проверки БД данные откатываются транзакциями; S3-тест удаляет только свои
синтетические объекты. Без `TEST_DATABASE_URL` / `TEST_S3` соответствующие тесты
пропускаются и это не считается приёмкой. Для изолированного прогона используйте
отдельный Compose project name и свободные порты. Результаты: [S01](docs/spec01-verification.md).

Проверка перезапуска и отказа S3 на отдельном тестовом проекте (пересоздаёт
контейнеры указанного проекта, сохраняет volumes):

```bash
python scripts/verify_infrastructure.py --env-file /tmp/test.env --project call-summary-test
```

## Совместимый сервер и аудиозависимости

`make server-cpu` запускает отдельный `call_summary.server:app` с прежним
`POST /transcribe` → `{"text": ...}`. Не запускайте одновременно на том же порту,
что и инфраструктурный API: например, `make server-cpu PORT=8011`.
`src/server.py` оставлен как совместимый импорт. Для Deepgram нужен
`DEEPGRAM_TOKEN`; реальный ASR smoke относится к spec 02. Импорт API и моделей
БД не загружает ASR. Модели совместимого сервера создаются один раз при старте.

Основные зависимости включают CPU faster-whisper/sherpa-onnx, ffmpeg и libsndfile.
CUDA-библиотеки доступны через `uv sync --extra gpu` и `make server-gpu`;
нужны совместимый NVIDIA driver и GPU. GPU-контейнер не входит в проверенный
CPU Compose; потребуется отдельный образ/runtime и явное выделение устройства.
Старый экспериментальный PyTorch/pyannote-стек доступен через extra `experimental`.
Локальный Docker сам по себе не даёт офлайн ASR/LLM.

## Backup и восстановление

Для согласованного локального backup остановите все пишущие процессы:

```bash
docker compose stop api worker
mkdir -p backups
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -n call_summary' > backups/call_summary.dump
```

Аудио копируйте отдельно через S3 API, не копированием `minio_data`. Установленным
`mc` создайте alias `audio` с endpoint хоста и ключами приложения, затем:

```bash
mc mirror audio/call-audio backups/call-audio
```

Храните рядом манифест относительных ключей, размеров и SHA-256 каждого объекта;
проверьте его по реально прочитанным байтам. Не используйте ETag вместо SHA-256.
Не возобновляйте запись до окончания обеих копий. После успешного backup:

```bash
docker compose start api worker
```

Восстановление сначала репетируется в отдельном проекте на пустых volumes.
Поднимите только db/minio, создайте bucket через storage-init. Init БД создаст
роли и пустую схему. При остановленных API/worker восстановите дамп:

```bash
docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --exit-on-error --clean --if-exists' < backups/call_summary.dump
mc mirror backups/call-audio audio/call-audio
make migrate
make bootstrap
```

Проверьте Alembic head, количество строк, связи, значения и состояние identity
последовательностей (дамп содержит sequence set), UUID/storage_key, перечень
объектов, размеры и SHA-256. Затем запускайте API/worker. Backup включает историю
Alembic; аудиотом не является форматом импорта Supabase. Дампы и аудио не добавлять
в Git. Этот runbook описывает локальное восстановление; перенос — spec 06.
