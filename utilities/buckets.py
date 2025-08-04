#!/usr/bin/env python3
"""
Python version of the TypeScript task bucket names configuration.
Maps task names to their corresponding bucket names for dev and prod environments.
"""

# Development environment task bucket names
TASK_BUCKET_NAMES_DEV = {
    'intro': 'levante-intro-dev',
    'vocab': 'levante-vocabulary-dev',
    'memorygame': 'levante-memory-dev',
    'roarinference': 'roar-inference',
    'adultreasoning': 'levante-math-dev',
    'heartsandflowers': 'levante-hearts-and-flowers-dev',
    'egmamath': 'levante-math-dev',
    'matrixreasoning': 'levante-pattern-matching-dev',
    'samedifferentselection': 'levante-same-different-dev',
    'trog': 'levante-sentence-understanding-dev',
    'mentalrotation': 'levante-shape-rotation-dev',
    'theoryofmind': 'levante-stories-dev',
    'shared': 'levante-tasks-shared-dev',
}

# Production environment task bucket names
TASK_BUCKET_NAMES_PROD = {
    'intro': 'levante-intro-prod',
    'vocab': 'levante-vocabulary-prod',
    'memorygame': 'levante-memory-prod',
    'roarinference': 'roar-inference',
    'adultreasoning': 'levante-math-prod',
    'heartsandflowers': 'levante-hearts-and-flowers-prod',
    'egmamath': 'levante-math-prod',
    'matrixreasoning': 'levante-pattern-matching-prod',
    'samedifferentselection': 'levante-same-different-prod',
    'trog': 'levante-sentence-understanding-prod',
    'mentalrotation': 'levante-shape-rotation-prod',
    'theoryofmind': 'levante-stories-prod',
    'shared': 'levante-tasks-shared-prod',
}

AUDIO_BUCKET_NAME_DEV = 'levante-audio-dev'
AUDIO_BUCKET_NAME_PROD = 'levante-audio-prod'

def get_bucket_name(task_name: str, environment: str = 'dev') -> str:
    """
    Get the bucket name for a specific task and environment.
    
    Args:
        task_name: Name of the task (e.g., 'vocab', 'egmamath')
        environment: Environment ('dev' or 'prod'), defaults to 'dev'
        
    Returns:
        Bucket name string, or None if task not found
    """
    if environment.lower() == 'prod':
        return TASK_BUCKET_NAMES_PROD.get(task_name.lower())
    else:
        return TASK_BUCKET_NAMES_DEV.get(task_name.lower())


def get_all_task_names() -> list:
    """
    Get a list of all available task names.
    
    Returns:
        List of task names
    """
    return list(TASK_BUCKET_NAMES_DEV.keys())


def get_dev_buckets() -> dict:
    """
    Get all development bucket mappings.
    
    Returns:
        Dictionary of dev bucket mappings
    """
    return TASK_BUCKET_NAMES_DEV.copy()


def get_prod_buckets() -> dict:
    """
    Get all production bucket mappings.
    
    Returns:
        Dictionary of prod bucket mappings
    """
    return TASK_BUCKET_NAMES_PROD.copy()


def is_valid_task(task_name: str) -> bool:
    """
    Check if a task name is valid.
    
    Args:
        task_name: Name of the task to check
        
    Returns:
        True if task exists, False otherwise
    """
    return task_name.lower() in TASK_BUCKET_NAMES_DEV


if __name__ == "__main__":
    # Example usage
    print("Testing buckets.py functionality...")
    
    # Test getting bucket names
    print(f"Vocab dev bucket: {get_bucket_name('vocab', 'dev')}")
    print(f"Vocab prod bucket: {get_bucket_name('vocab', 'prod')}")
    print(f"Math dev bucket: {get_bucket_name('egmamath', 'dev')}")
    
    # Test getting all tasks
    print(f"\nAll available tasks: {get_all_task_names()}")
    
    # Test validation
    print(f"\nIs 'vocab' a valid task? {is_valid_task('vocab')}")
    print(f"Is 'invalid' a valid task? {is_valid_task('invalid')}") 