# Диаграммы

Три вида схемы — как в [dataroom-cms](https://github.com/sikuykus-lab/dataroom-cms):
**данные**, **взаимодействие пользователя**, **процессы администратора**.

Рендер: скопировать блок в [mermaid.live](https://mermaid.live).

## Схема данных

```mermaid
flowchart TB
  subgraph chat ["Telegram чат"]
    CMD["/fight /start"]
    CB["callback атаки"]
  end

  subgraph game ["game/"]
    ENG["battle_engine"]
    SH["shop + currency"]
    DB["SQLite"]
  end

  subgraph web ["miniapp/"]
    MA["WebApp витрина"]
  end

  CMD --> ENG
  CB --> ENG
  ENG --> DB
  SH --> DB
  MA --> SH
```

## Процесс пользователя

```mermaid
flowchart LR
  A["/start"] --> B["Карточка героя"]
  B --> C["/fight"]
  C --> D["Ходы по кнопкам"]
  D --> E{"Победа?"}
  E -->|да| F["Награда + рейтинг"]
  E -->|нет| G["Лечение / магазин"]
```

## Процессы администратора

```mermaid
flowchart TD
  R1[".env + deploy/"] --> R2["systemctl enable heroes-bot"]
  R2 --> R3["/admin — промо, магазин"]
  R3 --> R4["setup-heroes-shop.sh\nMini App за nginx"]
```
