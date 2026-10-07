import os

folder_path = "ikaros"  # Replace with the folder path whose file names you want to get

# Use the os module to list all files in the folder
file_names = os.listdir(folder_path)

# Print the file name list
for file_name in file_names:
    print(f'"data/Idle task/audio/{folder_path}/{file_name}",')
