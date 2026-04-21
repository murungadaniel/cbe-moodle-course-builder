# CBE Moodle Course Builder

Generate Moodle course (MBZ files) automatically from CSV data and XML templates. This project creates ready-to-import Moodle course backup files.

---

## Getting Started

### Prerequisites

- Python 3.7 or higher
- pip (Python package manager)

### Installation

1. Clone or download this repository to your computer.

2. Open a terminal and navigate to the project directory:
```bash
cd cbe-moodle-course-builder
```

3. Install the required Python packages:
```bash
pip install -r requirements.txt
```

---

## How to Use

### Step 1: Prepare Your Data

1. Ensure you have the `Automatic-Links.csv` file in the project folder
2. Make sure you have the `template` folder with the Moodle backup structure

### Step 2: Generate Course Backups from CSV Data

Run the first script to generate course backup folders:

```bash
python3 generate_templates.py
```

What this does:
- Reads the CSV file containing your course data
- Creates a folder for each course in the `generated_backups` directory. The `generated_backups` directory will be auto generated when you run the script, no need to create that directory yourself.
- Populates each folder with course content and XML configuration files

### Step 3: Create Moodle Backup Files (MBZ)

After the backups are generated, run the second script to convert them into Moodle backup files:

```bash
python3 create_mbz_files.py
```

What this does:
- Takes all the generated backup folders from `generated_backups`
- Compresses each one into a `.mbz` file (Moodle backup format)
- Saves the `.mbz` files in the `moodle_mbz_backups` directory

### Step 4: Import into Moodle

1. Log in to your Moodle site as an administrator
2. Go to Site Administration > Courses > Restore
3. Upload each `.mbz` file from the `moodle_mbz_backups` folder

---

## Project Structure

- `generate_templates.py` - Generates course backups from CSV data
- `create_mbz_files.py` - Converts backup folders into Moodle backup files
- `Automatic-Links.csv` - Your course data (subject, topics, links)
- `template/` - Template folder with Moodle backup structure
- `generated_backups/` - Output folder for generated course backup folders
- `moodle_mbz_backups/` - Output folder for final Moodle backup files
- `requirements.txt` - Python package dependencies

---

