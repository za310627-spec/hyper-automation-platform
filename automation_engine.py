#!/usr/bin/env python3
"""
Hyper Automation Platform - Automation Engine

This script updates the dashboard_data.json file with status and progress information.
It accepts a status argument (e.g., 'Running' or 'Completed') and updates the JSON file
maintaining the structure: {"process_name": "...", "status": "...", "progress": "..."}.

Author: Hyper Automation Platform
Version: 2.0.0
"""

import json
import sys
import logging
from pathlib import Path
from datetime import datetime

# ============================================================================
# Configuration & Logging
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('automation_engine.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


# ============================================================================
# Constants
# ============================================================================

DASHBOARD_DATA_FILE = "dashboard_data.json"
DEFAULT_PROCESS_NAME = "Hyper Automation Process"
VALID_STATUSES = ["Running", "Completed", "Failed", "Pending", "Paused"]


# ============================================================================
# Dashboard Data Manager
# ============================================================================

class DashboardDataManager:
    """Manages dashboard data updates."""
    
    def __init__(self, filepath: str = DASHBOARD_DATA_FILE):
        """
        Initialize the dashboard data manager.
        
        Args:
            filepath: Path to the dashboard data JSON file
        """
        self.filepath = filepath
    
    def load_data(self) -> dict:
        """
        Load existing dashboard data from file.
        
        Returns:
            Dictionary containing dashboard data, or empty structure if file doesn't exist
        """
        try:
            file_path = Path(self.filepath)
            if file_path.exists():
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    logger.info(f"Loaded existing dashboard data from {self.filepath}")
                    return data
            else:
                logger.info(f"File {self.filepath} does not exist, creating new structure")
                return {
                    "process_name": DEFAULT_PROCESS_NAME,
                    "status": "Pending",
                    "progress": 0,
                    "last_updated": datetime.now().isoformat()
                }
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from {self.filepath}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to load data from {self.filepath}: {str(e)}")
            raise
    
    def update_status(self, status: str, progress: int = None) -> dict:
        """
        Update the status and optionally progress in the dashboard data.
        
        Args:
            status: The new status (must be one of VALID_STATUSES)
            progress: Optional progress value (0-100)
            
        Returns:
            Updated data dictionary
        """
        if status not in VALID_STATUSES:
            raise ValueError(
                f"Invalid status '{status}'. Valid options are: {', '.join(VALID_STATUSES)}"
            )
        
        if progress is not None:
            if not isinstance(progress, int) or progress < 0 or progress > 100:
                raise ValueError("Progress must be an integer between 0 and 100")
        
        # Load current data
        data = self.load_data()
        
        # Update status
        data["status"] = status
        logger.info(f"Updated status to: {status}")
        
        # Update progress if provided
        if progress is not None:
            data["progress"] = progress
            logger.info(f"Updated progress to: {progress}%")
        
        # Update timestamp
        data["last_updated"] = datetime.now().isoformat()
        
        return data
    
    def save_data(self, data: dict) -> None:
        """
        Save dashboard data to file.
        
        Args:
            data: Dictionary to save
        """
        try:
            file_path = Path(self.filepath)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Ensure required fields exist
            if "process_name" not in data:
                data["process_name"] = DEFAULT_PROCESS_NAME
            if "status" not in data:
                data["status"] = "Pending"
            if "progress" not in data:
                data["progress"] = 0
            if "last_updated" not in data:
                data["last_updated"] = datetime.now().isoformat()
            
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Dashboard data successfully saved to {self.filepath}")
            logger.info(f"Current data: {json.dumps(data, indent=2)}")
        except Exception as e:
            logger.error(f"Failed to save data to {self.filepath}: {str(e)}")
            raise
    
    def update_and_save(self, status: str, progress: int = None) -> dict:
        """
        Update status and/or progress and save to file.
        
        Args:
            status: The new status
            progress: Optional progress value (0-100)
            
        Returns:
            Updated data dictionary
        """
        data = self.update_status(status, progress)
        self.save_data(data)
        return data


# ============================================================================
# Main Entry Point
# ============================================================================

def print_usage():
    """Print usage information."""
    print("\nUsage: python automation_engine.py <status> [progress]")
    print(f"\nValid statuses: {', '.join(VALID_STATUSES)}")
    print("\nExamples:")
    print("  python automation_engine.py Running")
    print("  python automation_engine.py Running 50")
    print("  python automation_engine.py Completed 100")
    print()


def main():
    """Main entry point for the automation engine."""
    try:
        # Check command line arguments
        if len(sys.argv) < 2:
            logger.error("Missing required status argument")
            print_usage()
            sys.exit(1)
        
        status = sys.argv[1]
        progress = None
        
        # Parse optional progress argument
        if len(sys.argv) >= 3:
            try:
                progress = int(sys.argv[2])
            except ValueError:
                logger.error(f"Progress must be an integer, got: {sys.argv[2]}")
                print_usage()
                sys.exit(1)
        
        # Create manager and update data
        manager = DashboardDataManager()
        updated_data = manager.update_and_save(status, progress)
        
        # Print summary
        print("\n" + "=" * 60)
        print("DASHBOARD DATA UPDATE SUMMARY")
        print("=" * 60)
        print(f"Process Name: {updated_data.get('process_name', 'N/A')}")
        print(f"Status: {updated_data.get('status', 'N/A')}")
        print(f"Progress: {updated_data.get('progress', 'N/A')}%")
        print(f"Last Updated: {updated_data.get('last_updated', 'N/A')}")
        print("=" * 60 + "\n")
        
        logger.info("Automation engine script completed successfully")
        sys.exit(0)
        
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        print_usage()
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
