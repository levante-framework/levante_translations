import pandas as pd

def compare_csv_files(file1, file2, output_file='output_diff.csv'):
    """
    Compares columns with the same names in two CSV files and saves the differing rows to an output file.
    
    Parameters:
    file1 (str): Path to the first CSV file.
    file2 (str): Path to the second CSV file.
    output_file (str): Path for saving the CSV file with differing rows. Defaults to 'output_diff.csv'.
    
    Raises:
    FileNotFoundError: If either of the CSV files is not found.
    ValueError: If there are no common columns between the two CSV files.
    """
    try:
        # Load the CSV files into dataframes
        csv1 = pd.read_csv(file1)
        csv2 = pd.read_csv(file2)

        # Identify columns that exist in both dataframes
        common_columns = csv1.columns.intersection(csv2.columns)
        
        # Ensure there are common columns to compare
        if len(common_columns) == 0:
            raise ValueError("No common columns found between the two CSV files.")

        # Find rows that differ across any of the common columns
        diff_rows = pd.concat([csv1[common_columns], csv2[common_columns]]).drop_duplicates(keep=False)

        # Save the differing rows to an output CSV file
        diff_rows.to_csv(output_file, index=False)
        print(f"Comparison complete. Output saved to '{output_file}'.")
        
    except FileNotFoundError as e:
        print(f"Error: {e}")
    except ValueError as ve:
        print(f"Error: {ve}")

# Example usage:
# compare_csv_files('item-bank-translations-v1.csv', 'translation-items-v2.csv')