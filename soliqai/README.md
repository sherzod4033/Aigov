# 🏛️ SoliqAI

Локальный ИИ-помощник по налогам.

## 📋 Технологический стек

| Компонент | Технология |
|-----------|------------|
| Frontend | React 19 + Tailwind CSS + Vite |
| Backend | FastAPI (Python 3.12) |
| Векторная БД | ChromaDB |
| База данных | PostgreSQL + asyncpg |
| Локальная ИИ | Gemma 3n (Ollama) |
| Улучшение | OpenAI GPT-4.1-mini |
| OCR | Tesseract |

## 🚀 Быстрый старт

### Предварительные требования

- Python 3.12+
- Node.js 20+
- PostgreSQL 14+
- Ollama (с моделью gemma3n:e4b)
- Tesseract OCR

### 1. Клонирование и настройка

```bash
cd soliqai

# Backend
cd backend
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# или: venv\Scripts\activate  # Windows

pip install -r requirements.txt

# Настройка переменных окружения
cp .env.example .env
# Отредактируйте .env файл
```

### 2. Настройка базы данных

```bash
# Создать базу данных PostgreSQL
createdb soliqai_db

# Инициализация таблиц
cd backend
source venv/bin/activate
python -c "import asyncio; from app.core.database import init_db; asyncio.run(init_db())"
```

### 3. Запуск backend

```bash
cd backend
source venv/bin/activate

# Режим разработки
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

# Или для production
uvicorn app.main:app --host 0.0.0.0 --port 8001 --workers 4
```

API будет доступен по адресу: http://localhost:8001

Документация API: http://localhost:8001/api/v1/docs

### 4. Запуск frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend будет доступен по адресу: http://localhost:5173

### 5. Настройка Ollama

```bash
# Установка Ollama (если не установлен)
curl -fsSL https://ollama.com/install.sh | sh

# Загрузка модели
ollama pull gemma3n:e4b

# Запуск сервера
ollama serve
```

## 🔒 Безопасность

### Перед production-развертыванием:

1. **Измените SECRET_KEY** в `.env`:
   ```bash
   openssl rand -hex 32
   ```

2. **Ограничьте CORS** в `.env`:
   ```
   CORS_ORIGINS=http://localhost:5173,https://yourdomain.com
   ```

3. **Используйте сильные пароли** для базы данных

4. **Установите переменную окружения**:
   ```
   ENVIRONMENT=production
   ```

## 🧪 Тестирование

```bash
cd backend
source venv/bin/activate
python -m unittest discover -v tests/
```

## 📊 Health Checks

- `GET /health` - Базовая проверка работоспособности
- `GET /ready` - Проверка готовности всех зависимостей (БД, ChromaDB)

## 📁 Структура проекта

```
soliqai/
├── backend/
│   ├── app/
│   │   ├── api/           # API endpoints
│   │   ├── core/          # Конфигурация, БД, безопасность
│   │   ├── models/        # SQLModel модели
│   │   └── services/      # Бизнес-логика
│   ├── tests/             # Юнит-тесты
│   ├── .env.example       # Шаблон переменных окружения
│   └── requirements.txt   # Python зависимости
├── frontend/
│   ├── src/
│   │   ├── pages/         # React страницы
│   │   ├── components/    # UI компоненты
│   │   └── services/      # API клиент
│   └── package.json
└── README.md
```

## 🔧 Переменные окружения

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `OPENAI_API_KEY` | Ключ OpenAI API | - |
| `SECRET_KEY` | JWT секретный ключ | Автогенерация |
| `POSTGRES_*` | Настройки PostgreSQL | localhost |
| `CORS_ORIGINS` | Разрешенные origins | * |
| `ENVIRONMENT` | Среда (development/production) | development |

## 👥 Роли пользователей

- **admin** - Полный доступ (документы, FAQ, настройки, пользователи)
- **content_manager** - Управление документами и FAQ
- **user** - Только чат

## 📝 Лицензия

© 2026 Хукумати Ҷумҳурии Тоҷикистон. Ҳамаи ҳуқуқҳо ҳифз шудаанд.
