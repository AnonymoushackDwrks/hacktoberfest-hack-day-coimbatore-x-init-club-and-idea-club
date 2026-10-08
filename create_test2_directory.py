import os

# Define the path for the new directory
new_dir = os.path.join("D:\\hacktoberfest-hack-day-coimbatore-x-init-club-and-idea-club", "Test 2")

# Create the directory if it does not exist
if not os.path.exists(new_dir):
    os.makedirs(new_dir)