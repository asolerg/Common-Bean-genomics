# Initialize a new Git repository
git init

# Add a README file
echo "# Common-Bean-genomics" >> README.md

# Stage all files (app.py, bcmv_markers.db, requirements.txt, README.md)
git add .

# Commit the files
git commit -m "Initial commit with Streamlit app and SQLite database"

# Rename the default branch to main
git branch -M main

# Link your local repository to your remote GitHub repository
git remote add origin https://github.com/asolerg/Common-Bean-genomics.git

# Push the code to GitHub
git push -u origin main# Common-Bean-genomics
