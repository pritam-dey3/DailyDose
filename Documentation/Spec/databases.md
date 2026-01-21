# Storage, Input UX and Tracking

## Storage / Input UX

The system uses a single YAML file (`library.yaml`) to define both the content (doses) and the configuration (tag demands). This keeps everything in one place while maintaining a flat structure for doses.

### Unified Storage (`library.yaml`)

The file has two main sections:

1.  **Tags**: Defines the demand (time pressure multiplier) for each category.
2.  **Doses**: A flat list of messages, each assigned a specific tag.

```yaml
tags:
  exercise: 1.5
  nutrition: 1.2
  finance: 0.5

doses:
  - id: complex_movement
    tag: exercise
    frequency:
      type: at-least
      count: 1
      period: day
    message: "Do a compound movement today (Squat, Deadlift, or Bench)."
  - id: walk_10k
    tag: exercise
    frequency:
      type: at-least
      count: 3
      period: week
    message: "Go for a long walk aiming for 10k steps."
  - id: drink_water
    tag: nutrition
    frequency:
      type: at-least
      count: 1
      period: day
    message: "Drink 8 glasses of water."
  - id: check_balance
    tag: finance
    frequency:
      type: exactly
      count: 1
      period: month
    message: "Review your monthly expenses."
```

### Tabular Format

#### Tags

| Tag       | Demand |
| --------- | ------ |
| exercise  | 1.5    |
| nutrition | 1.2    |
| finance   | 0.5    |

#### Doses

| ID               | Tag       | Type     | Count | Period | Message                                                   |
| ---------------- | --------- | -------- | ----- | ------ | --------------------------------------------------------- |
| complex_movement | exercise  | at-least | 1     | day    | Do a compound movement today (Squat, Deadlift, or Bench). |
| walk_10k         | exercise  | at-least | 3     | week   | Go for a long walk aiming for 10k steps.                  |
| drink_water      | nutrition | at-least | 1     | day    | Drink 8 glasses of water.                                 |
| check_balance    | finance   | exactly  | 1     | month  | Review your monthly expenses.                             |

## Tracking

We need a minimal state engine to track history and enforce quotas.

- **History Log:**
  - Structure: `{ dose_id: days_since_last_shown, count_in_current_period }`
