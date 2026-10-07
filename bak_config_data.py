import shutil
import os

def backup_files(file_paths, destination_directory):
    # Check whether the target directory exists and create it if not
    if not os.path.exists(destination_directory):
        os.makedirs(destination_directory)

    for source_file_path in file_paths:
        # Check whether the source file exists
        if os.path.exists(source_file_path):
            # Get the file name
            file_name = os.path.basename(source_file_path)

            # Build the target file path
            destination_file_path = os.path.join(destination_directory, file_name)

            # Check whether the target file exists and delete it if so
            if os.path.exists(destination_file_path):
                os.remove(destination_file_path)

            # Copy the file, overwriting any existing file
            shutil.copy2(source_file_path, destination_file_path)
            print(f"file '{file_name}' Back up to '{destination_directory}'")
        else:
            print(f"file '{source_file_path}' Not found. Skipping.")

def backup_dir(source_path, destination_directory):
    # Check whether the target directory exists and create it if not
    if not os.path.exists(destination_directory):
        os.makedirs(destination_directory)

    # Build the target path
    destination_path = os.path.join(destination_directory, os.path.basename(source_path))

    try:
        # Check whether the source path is a file or a folder
        if os.path.isfile(source_path):
            # If it is a file, check whether the target file exists and delete it if so
            if os.path.exists(destination_path):
                os.remove(destination_path)

            # Copy the file using shutil.copy2
            shutil.copy2(source_path, destination_path)
            print(f"file '{source_path}' Back up to '{destination_directory}'")
        elif os.path.isdir(source_path):
            # If it is a folder, check whether the target folder exists and delete it if so
            if os.path.exists(destination_path):
                shutil.rmtree(destination_path)

            # Copy the folder using shutil.copytree
            shutil.copytree(source_path, destination_path)
            print(f"folder '{source_path}' Back up to '{destination_directory}'")
        else:
            print(f"Unsupported source type: '{source_path}'")
    except Exception as e:
        print(f"Error during backup: {e}")

# Get the absolute path of the directory containing the current script
current_directory = os.path.abspath(os.path.dirname(__file__))
# Example usage
file_paths_to_backup = [
    os.path.join(current_directory, "config.json")
]
dir_path_to_backup = os.path.join(current_directory, "data")
dir_path_to_backup2 = os.path.join(current_directory, "out")

destination_directory_path = os.path.join(current_directory, "backup")  # Replace with the actual backup directory path

backup_files(file_paths_to_backup, destination_directory_path)
backup_dir(dir_path_to_backup, destination_directory_path)
backup_dir(dir_path_to_backup2, destination_directory_path)

print("Run finished")
