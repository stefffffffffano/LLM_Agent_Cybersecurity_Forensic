"""Function to concatenate .log files (given their directory) into a single str to be returned as output"""
import os

def concatenate_logs(directory: str) -> str:
    """
    Concatenate all .log files in the given directory into a single string.
    
    Args:
        directory (str): The path to the directory containing .log files.
        
    Returns:
        str: The concatenated content of all .log files.
    """
    log_content = ""
    i = 1
    # Iterate through all files in the directory
    for filename in os.listdir(directory):
        if filename.endswith(".log"):
            file_path = os.path.join(directory, filename)
            with open(file_path, 'r') as file:
                log_content += f"Log file number {i}:\n" + file.read() + "\n\n"  
            i+=1
    return log_content