# FIFA World Cup 2026 Match Prediction & Tournament Simulation

## Overview

This project is an end-to-end machine learning pipeline for predicting FIFA World Cup 2026 matches and simulating the entire tournament using Monte Carlo simulation.

The system combines historical international football match results, FIFA rankings, squad statistics, and Elo ratings to train an ensemble of gradient boosting models. The trained models are then used to simulate thousands of tournament iterations and estimate each team's probability of reaching every stage of the competition.

The project also integrates MLflow for experiment tracking, model versioning, and artifact management.

---

## Features

- Automated data import into MySQL
- Data cleaning and preprocessing
- Feature engineering
- Time-aware cross validation (TimeSeriesSplit)
- Hyperparameter tuning using GridSearchCV
- Ensemble learning with:
  - XGBoost
  - LightGBM
  - CatBoost
- Optimized ensemble weights
- Monte Carlo World Cup simulation
- Elo rating updates during simulation
- Head-to-head statistics
- Automatic visualization generation
- MLflow experiment tracking
- Model persistence

---

## Project Structure

```
project/
│
├── data/
│   ├── raw csv files
│   ├── tournament_groups.csv
│   └── monte_carlo_predictions.csv
│
├── saved_models/
│
├── visualization.py
├── simulate.py
├── perfect_pipeline.py
├── helpers.py
├── feature_engineering.py
├── model_training.py
├── database_connection.py
├── database_loader.py
├── perfect_config.py
├── main.py
└── requirements.txt
```

---

## Machine Learning Pipeline

The training pipeline consists of:

1. Import raw datasets into MySQL
2. Load historical data
3. Data preprocessing
4. Feature engineering
5. Prepare training data
6. Hyperparameter tuning
7. Model training
8. Time-series cross validation
9. Ensemble weight optimization
10. Evaluation
11. Model saving

---

## Engineered Features

Examples of generated features include:

- FIFA Ranking
- FIFA Points
- Elo Rating
- Elo Difference
- Elo Win Probability
- Ranking Difference
- Ranking Tier
- Team Market Value
- Average Squad Age
- Last 5 Match Win Rate
- Last 5 Goal Difference
- Head-to-Head Statistics
- Home Advantage
- Days of Rest
- Match Importance
- Friendly/Tournament Indicator

---

## Models

Three gradient boosting regressors are trained independently.

- XGBoost Regressor
- LightGBM Regressor
- CatBoost Regressor

Their predictions are combined using optimized ensemble weights obtained from out-of-fold predictions.

---

## Tournament Simulation

After training, the project simulates the FIFA World Cup using Monte Carlo simulation.

Each simulation includes:

- Group Stage
- Round of 32
- Round of 16
- Quarter Finals
- Semi Finals
- Third Place Match
- Final

Team statistics such as Elo ratings and recent form are updated dynamically throughout the tournament.

The simulation is repeated thousands of times to estimate:

- Qualification probability
- Quarter-final probability
- Semi-final probability
- Final probability
- Championship probability

---

## MLflow Integration

MLflow is used to track:

- Hyperparameters
- Ensemble weights
- Evaluation metrics
- Feature list
- Trained models
- Simulation outputs

To launch the MLflow UI:

```bash
mlflow ui
```

---

## Visualizations

The project automatically generates visualizations including:

- Prediction vs Actual
- Residual Plot
- Feature Importance
- Tournament Probability Charts
- Simulation Statistics

---

## Configuration

Project settings are stored in `perfect_config.py`.

Examples include:

- Number of CV splits
- Random seed
- Monte Carlo iterations
- Elo parameters
- Database configuration
- File paths

---

## How to Run

### Prerequisites

#### 1. MySQL Database
You must have MySQL running locally. If you don't have it installed:

- **Download**: https://dev.mysql.com/downloads/mysql/
- **Installation**: Follow the official guide for your OS
- **Start the server**:
  - **Windows**: MySQL typically starts as a service automatically
  - **Mac**: `brew services start mysql` (if installed via Homebrew)
  - **Linux**: `sudo systemctl start mysql`

#### 2. Python 3.8+
Verify Python is installed:
```bash
python --version
```

---

### Setup Instructions

#### Step 1: Navigate to Project Directory
```bash
cd project
```

#### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

#### Step 3: Configure Database Connection (Optional)
Edit `code/perfect_config.py` if your MySQL setup differs:

```python
@dataclass
class DatabaseConfig:
    user = "root"           # Your MySQL username
    password = ""           # Your MySQL password (empty if none)
    host = "localhost"      # MySQL host
    port = 3306             # MySQL port
    database = "ww26_predictor"  # Database name (auto-created)
```

Default assumes:
- Username: `root`
- Password: (empty)
- Host: `localhost`
- Port: `3306`

#### Step 4: Run the Pipeline
```bash
cd code
python main.py
```

---

### What Happens When You Run

The pipeline executes automatically in this order:

1. **Data Import**: Raw CSVs imported into MySQL
2. **Data Loading**: Historical matches loaded from database
3. **Preprocessing**: Cleaning, handling missing values
4. **Feature Engineering**: 15+ features (Elo, form, H2H, etc.)
5. **Model Training**: XGBoost, LightGBM, CatBoost trained with GridSearch
6. **Cross-Validation**: Time-series 5-fold CV with OOF predictions
7. **Ensemble Optimization**: Weights optimized via Nelder-Mead
8. **Evaluation**: Metrics computed (MAE, RMSE, R²)
9. **Tournament Simulation**: 1,000 Monte Carlo simulations
10. **Visualization**: Charts generated (predictions, importance, probabilities)
11. **MLflow Logging**: All results tracked in local MLflow

---

### Outputs

After running, you'll find:

| File | Location | Description |
|------|----------|-------------|
| Trained Models | `saved_models/trained_models.pkl` | Serialized ensemble models |
| Predictions | `data/monte_carlo_predictions.csv` | Team championship probabilities |
| Charts | `outputs/*.png` | 9 visualizations (feature importance, predictions, etc.) |
| MLflow DB | `mlflow.db` | Local experiment tracking |

---

### Viewing Results

#### MLflow Dashboard
To explore training metrics and artifacts:

```bash
mlflow ui
```
Then open: `http://localhost:5000`

#### Simulation Results
Check the top contenders:
```bash
cat data/monte_carlo_predictions.csv
```

---

### Troubleshooting

**Error: `Connection refused` or `Can't connect to MySQL server`**
- Solution: Ensure MySQL is running
  - Windows: Check Services → MySQL is running
  - Mac: `brew services start mysql`
  - Linux: `sudo systemctl start mysql`

**Error: `No such file or directory: 'data/results.csv'`**
- Solution: Ensure you're in the `code/` directory when running:
  ```bash
  cd project/code
  python main.py
  ```

**Error: `ACCESS DENIED for user 'root'@'localhost'`**
- Solution: Update database credentials in `code/perfect_config.py` with your actual MySQL username/password

**Error: `mlflow.db` not found**
- Solution: This is created automatically on first run; if it fails, check MySQL connection

---

### Notes

- **First run takes ~5-10 minutes** (data import + model training + 1000 simulations)
- **Models are cached**: Subsequent runs skip training if `saved_models/trained_models.pkl` exists
- **Delete cached models** to retrain: `rm saved_models/trained_models.pkl`
- **All paths are relative** to the `code/` directory

---

## Outputs

The project generates:

- Trained models
- MLflow experiments
- Prediction metrics
- Tournament probabilities
- Simulation CSV
- Visualizations

---

## Technologies

- Python
- Pandas
- NumPy
- Scikit-learn
- XGBoost
- LightGBM
- CatBoost
- SQLAlchemy
- MySQL
- MLflow
- Matplotlib

---

## video and powerpoint link
- https://drive.google.com/drive/folders/160EGCbBADNZWeRs_8bF7uNvG-WSRPXJa?usp=drive_link

## License

This project is intended for educational and research purposes.