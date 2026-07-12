#!/usr/bin/env python3
"""
Hyper Automation Platform - Automation Engine

This module provides a robust automation engine for web scraping, data processing,
and dashboard data collection. It utilizes Playwright for dynamic content and
BeautifulSoup for static content parsing.

Features:
    - Web scraping with Playwright and BeautifulSoup
    - Data processing and transformation
    - Error handling and retry logic
    - Logging and monitoring
    - Dashboard data aggregation
    - Asynchronous operations support

Author: Hyper Automation Platform
Version: 1.0.0
"""

import asyncio
import json
import logging
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import time
from pathlib import Path

try:
    from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeoutError
except ImportError:
    print("Warning: Playwright not installed. Install with: pip install playwright")
    print("Also run: playwright install")

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Warning: BeautifulSoup4 not installed. Install with: pip install beautifulsoup4")

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# ============================================================================
# Configuration & Constants
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('automation_engine.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class DataSourceType(Enum):
    """Supported data source types."""
    STATIC_HTML = "static_html"
    DYNAMIC_JS = "dynamic_js"
    API = "api"
    CSV = "csv"


class ConversionStage(Enum):
    """Conversion funnel stages."""
    LANDING_PAGE = "landing_page"
    SIGN_UP = "sign_up"
    EMAIL_VERIFY = "email_verification"
    PLAN_SELECT = "plan_selection"
    PAYMENT = "payment"
    ACCOUNT_SETUP = "account_setup"


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class AutomationMetrics:
    """Metrics for an automation workflow."""
    name: str
    automation_type: str
    status: str
    executions: int
    success_rate: float
    last_run: str
    next_run: Optional[str] = None
    error_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class ConversionData:
    """Data for a conversion funnel stage."""
    stage: str
    visitors: int
    conversion_rate: float
    drop_rate: float
    average_time_seconds: int
    timestamp: str


@dataclass
class DashboardData:
    """Aggregated dashboard data."""
    timestamp: str
    active_automations: int
    conversion_rate: float
    total_revenue: float
    processed_tasks: int
    automations: List[AutomationMetrics]
    funnel_stages: List[ConversionData]
    metrics: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'timestamp': self.timestamp,
            'active_automations': self.active_automations,
            'conversion_rate': self.conversion_rate,
            'total_revenue': self.total_revenue,
            'processed_tasks': self.processed_tasks,
            'automations': [a.to_dict() for a in self.automations],
            'funnel_stages': [asdict(f) for f in self.funnel_stages],
            'metrics': self.metrics
        }


# ============================================================================
# Session Management
# ============================================================================

class SessionManager:
    """Manages HTTP sessions with retry logic."""
    
    def __init__(self, retries: int = 3, backoff_factor: float = 0.5):
        """
        Initialize session manager.
        
        Args:
            retries: Number of retry attempts
            backoff_factor: Backoff factor for retries
        """
        self.retries = retries
        self.backoff_factor = backoff_factor
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """Create session with retry strategy."""
        session = requests.Session()
        retry_strategy = Retry(
            total=self.retries,
            backoff_factor=self.backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            method_whitelist=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Hyper Automation Platform/1.0)'
        })
        return session
    
    def get(self, url: str, timeout: int = 10, **kwargs) -> requests.Response:
        """
        GET request with error handling.
        
        Args:
            url: URL to request
            timeout: Request timeout in seconds
            **kwargs: Additional arguments for requests.get()
            
        Returns:
            Response object
        """
        try:
            response = self.session.get(url, timeout=timeout, **kwargs)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            logger.error(f"HTTP request failed for {url}: {str(e)}")
            raise
    
    def close(self):
        """Close session."""
        self.session.close()


# ============================================================================
# Web Scrapers
# ============================================================================

class StaticContentScraper:
    """Scrapes static HTML content using BeautifulSoup."""
    
    def __init__(self, session_manager: SessionManager):
        """
        Initialize static scraper.
        
        Args:
            session_manager: SessionManager instance
        """
        self.session_manager = session_manager
    
    def scrape(self, url: str, selector: str) -> List[Dict[str, str]]:
        """
        Scrape static content from URL.
        
        Args:
            url: URL to scrape
            selector: CSS selector for target elements
            
        Returns:
            List of extracted data dictionaries
        """
        try:
            logger.info(f"Scraping static content from {url}")
            response = self.session_manager.get(url)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            elements = soup.select(selector)
            if not elements:
                logger.warning(f"No elements found with selector: {selector}")
                return []
            
            results = []
            for element in elements:
                data = {
                    'text': element.get_text(strip=True),
                    'html': str(element),
                    'attrs': dict(element.attrs)
                }
                results.append(data)
            
            logger.info(f"Successfully scraped {len(results)} elements from {url}")
            return results
            
        except Exception as e:
            logger.error(f"Static scraping failed for {url}: {str(e)}")
            raise


class DynamicContentScraper:
    """Scrapes dynamic JavaScript-rendered content using Playwright."""
    
    def __init__(self, headless: bool = True, timeout: int = 30000):
        """
        Initialize dynamic scraper.
        
        Args:
            headless: Run browser in headless mode
            timeout: Page timeout in milliseconds
        """
        self.headless = headless
        self.timeout = timeout
        self.browser: Optional[Browser] = None
    
    async def initialize(self):
        """Initialize Playwright browser."""
        try:
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(headless=self.headless)
            logger.info("Playwright browser initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Playwright: {str(e)}")
            raise
    
    async def scrape(self, url: str, selector: str, wait_selector: Optional[str] = None) -> List[Dict[str, str]]:
        """
        Scrape dynamic content from URL.
        
        Args:
            url: URL to scrape
            selector: CSS selector for target elements
            wait_selector: CSS selector to wait for before scraping
            
        Returns:
            List of extracted data dictionaries
        """
        page = None
        try:
            if not self.browser:
                await self.initialize()
            
            logger.info(f"Scraping dynamic content from {url}")
            page = await self.browser.new_page()
            await page.goto(url, wait_until='networkidle')
            
            # Wait for specific element if provided
            if wait_selector:
                await page.wait_for_selector(wait_selector, timeout=self.timeout)
            
            # Wait for target elements
            await page.wait_for_selector(selector, timeout=self.timeout)
            
            # Extract data
            results = await page.evaluate(f"""
                () => {{
                    return Array.from(document.querySelectorAll('{selector}')).map(el => ({{
                        text: el.innerText,
                        html: el.innerHTML,
                        attrs: Array.from(el.attributes).reduce((acc, attr) => {{
                            acc[attr.name] = attr.value;
                            return acc;
                        }}, {{}})
                    }}));
                }}
            """)
            
            logger.info(f"Successfully scraped {len(results)} dynamic elements from {url}")
            return results
            
        except PlaywrightTimeoutError as e:
            logger.error(f"Timeout waiting for element in {url}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Dynamic scraping failed for {url}: {str(e)}")
            raise
        finally:
            if page:
                await page.close()
    
    async def close(self):
        """Close Playwright browser."""
        if self.browser:
            await self.browser.close()
            logger.info("Playwright browser closed")


class APIScraper:
    """Scrapes data from REST APIs."""
    
    def __init__(self, session_manager: SessionManager):
        """
        Initialize API scraper.
        
        Args:
            session_manager: SessionManager instance
        """
        self.session_manager = session_manager
    
    def fetch(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Fetch data from API endpoint.
        
        Args:
            url: API endpoint URL
            params: Query parameters
            
        Returns:
            Parsed JSON response
        """
        try:
            logger.info(f"Fetching data from API: {url}")
            response = self.session_manager.get(url, params=params)
            data = response.json()
            logger.info(f"Successfully fetched API data from {url}")
            return data
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from {url}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"API scraping failed for {url}: {str(e)}")
            raise


# ============================================================================
# Data Processing
# ============================================================================

class DataProcessor:
    """Processes and transforms scraped data."""
    
    @staticmethod
    def extract_metrics(data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Extract key metrics from data.
        
        Args:
            data: List of data items
            
        Returns:
            Dictionary of computed metrics
        """
        try:
            if not data:
                return {}
            
            metrics = {
                'total_items': len(data),
                'processed_at': datetime.now().isoformat(),
            }
            
            logger.info(f"Extracted metrics from {len(data)} items")
            return metrics
        except Exception as e:
            logger.error(f"Metric extraction failed: {str(e)}")
            raise
    
    @staticmethod
    def generate_automation_metrics(
        name: str,
        automation_type: str,
        executions: int,
        success_count: int
    ) -> AutomationMetrics:
        """
        Generate automation metrics.
        
        Args:
            name: Automation name
            automation_type: Type of automation
            executions: Total execution count
            success_count: Successful executions
            
        Returns:
            AutomationMetrics instance
        """
        success_rate = (success_count / executions * 100) if executions > 0 else 0
        
        return AutomationMetrics(
            name=name,
            automation_type=automation_type,
            status="active",
            executions=executions,
            success_rate=round(success_rate, 2),
            last_run=datetime.now().isoformat(),
            error_count=executions - success_count
        )
    
    @staticmethod
    def generate_conversion_data(
        stage: ConversionStage,
        visitors: int,
        conversions: int,
        average_time_seconds: int
    ) -> ConversionData:
        """
        Generate conversion funnel data.
        
        Args:
            stage: Conversion stage
            visitors: Number of visitors
            conversions: Number of conversions
            average_time_seconds: Average time in seconds
            
        Returns:
            ConversionData instance
        """
        conversion_rate = (conversions / visitors * 100) if visitors > 0 else 0
        drop_rate = 100 - conversion_rate
        
        return ConversionData(
            stage=stage.value,
            visitors=visitors,
            conversion_rate=round(conversion_rate, 2),
            drop_rate=round(drop_rate, 2),
            average_time_seconds=average_time_seconds,
            timestamp=datetime.now().isoformat()
        )


# ============================================================================
# Automation Engine
# ============================================================================

class AutomationEngine:
    """Main automation engine for orchestrating scrapers and processors."""
    
    def __init__(self):
        """Initialize automation engine."""
        self.session_manager = SessionManager()
        self.static_scraper = StaticContentScraper(self.session_manager)
        self.dynamic_scraper = DynamicContentScraper(headless=True)
        self.api_scraper = APIScraper(self.session_manager)
        self.data_processor = DataProcessor()
        logger.info("Automation engine initialized")
    
    async def collect_dashboard_data(self) -> DashboardData:
        """
        Collect all data for dashboard.
        
        Returns:
            Aggregated DashboardData instance
        """
        try:
            logger.info("Starting dashboard data collection")
            
            # Generate sample automation metrics
            automations = [
                self.data_processor.generate_automation_metrics(
                    "Email Campaign Auto", "Email", 3421, 3249
                ),
                self.data_processor.generate_automation_metrics(
                    "Lead Scoring Pipeline", "CRM", 1892, 1665
                ),
                self.data_processor.generate_automation_metrics(
                    "Social Media Scheduler", "Social", 562, 404
                ),
                self.data_processor.generate_automation_metrics(
                    "Invoice Generation Bot", "Finance", 2145, 1973
                ),
                self.data_processor.generate_automation_metrics(
                    "Data Sync Service", "Integration", 421, 189
                ),
            ]
            
            # Generate sample conversion funnel data
            funnel_stages = [
                self.data_processor.generate_conversion_data(
                    ConversionStage.LANDING_PAGE, 45230, 45230, 135
                ),
                self.data_processor.generate_conversion_data(
                    ConversionStage.SIGN_UP, 45230, 12890, 222
                ),
                self.data_processor.generate_conversion_data(
                    ConversionStage.EMAIL_VERIFY, 12890, 10654, 68
                ),
                self.data_processor.generate_conversion_data(
                    ConversionStage.PLAN_SELECT, 10654, 8792, 272
                ),
                self.data_processor.generate_conversion_data(
                    ConversionStage.PAYMENT, 8792, 6234, 175
                ),
                self.data_processor.generate_conversion_data(
                    ConversionStage.ACCOUNT_SETUP, 6234, 4412, 378
                ),
            ]
            
            # Calculate aggregate metrics
            total_executions = sum(a.executions for a in automations)
            total_successes = sum(int(a.executions * a.success_rate / 100) for a in automations)
            active_count = sum(1 for a in automations if a.status == "active")
            
            dashboard_data = DashboardData(
                timestamp=datetime.now().isoformat(),
                active_automations=active_count,
                conversion_rate=3.8,
                total_revenue=24500.0,
                processed_tasks=8942,
                automations=automations,
                funnel_stages=funnel_stages,
                metrics={
                    'total_executions': total_executions,
                    'total_successes': total_successes,
                    'overall_success_rate': round(total_successes / total_executions * 100, 2) if total_executions > 0 else 0,
                    'collection_duration_seconds': 0
                }
            )
            
            logger.info("Dashboard data collection completed successfully")
            return dashboard_data
            
        except Exception as e:
            logger.error(f"Dashboard data collection failed: {str(e)}")
            raise
    
    async def scrape_url(self, url: str, content_type: DataSourceType = DataSourceType.STATIC_HTML,
                        selector: str = "body") -> List[Dict[str, str]]:
        """
        Scrape content from URL based on content type.
        
        Args:
            url: URL to scrape
            content_type: Type of content source
            selector: CSS selector for extraction
            
        Returns:
            List of scraped data
        """
        try:
            logger.info(f"Starting scrape for {url} (type: {content_type.value})")
            
            if content_type == DataSourceType.DYNAMIC_JS:
                results = await self.dynamic_scraper.scrape(url, selector)
            else:  # Default to static HTML
                results = self.static_scraper.scrape(url, selector)
            
            logger.info(f"Scrape completed for {url}")
            return results
            
        except Exception as e:
            logger.error(f"Scrape failed for {url}: {str(e)}")
            raise
    
    def save_data(self, data: DashboardData, filepath: str = "dashboard_data.json"):
        """
        Save dashboard data to file.
        
        Args:
            data: DashboardData to save
            filepath: Output file path
        """
        try:
            output_path = Path(filepath)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w') as f:
                json.dump(data.to_dict(), f, indent=2)
            
            logger.info(f"Dashboard data saved to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save data to {filepath}: {str(e)}")
            raise
    
    async def run(self):
        """
        Run the automation engine.
        Collects data and saves to file.
        """
        try:
            logger.info("=== Starting Hyper Automation Engine ===")
            start_time = time.time()
            
            # Collect dashboard data
            dashboard_data = await self.collect_dashboard_data()
            
            # Save data
            self.save_data(dashboard_data)
            
            elapsed_time = time.time() - start_time
            logger.info(f"=== Automation Engine completed in {elapsed_time:.2f} seconds ===")
            
            return dashboard_data
            
        except Exception as e:
            logger.error(f"Automation engine failed: {str(e)}")
            raise
        finally:
            await self.cleanup()
    
    async def cleanup(self):
        """Clean up resources."""
        try:
            await self.dynamic_scraper.close()
            self.session_manager.close()
            logger.info("Resources cleaned up")
        except Exception as e:
            logger.error(f"Cleanup failed: {str(e)}")


# ============================================================================
# Main Entry Point
# ============================================================================

async def main():
    """Main entry point for the automation engine."""
    engine = None
    try:
        engine = AutomationEngine()
        result = await engine.run()
        
        # Print summary
        print("\n" + "="*60)
        print("DASHBOARD DATA SUMMARY")
        print("="*60)
        print(f"Active Automations: {result.active_automations}")
        print(f"Conversion Rate: {result.conversion_rate}%")
        print(f"Total Revenue: ${result.total_revenue:,.2f}")
        print(f"Processed Tasks: {result.processed_tasks:,}")
        print(f"Total Automations Monitored: {len(result.automations)}")
        print(f"Funnel Stages Tracked: {len(result.funnel_stages)}")
        print(f"Collection Timestamp: {result.timestamp}")
        print("="*60)
        print("\nData saved to: dashboard_data.json")
        
        return result
        
    except Exception as e:
        logger.error(f"Fatal error in main: {str(e)}")
        sys.exit(1)
    finally:
        if engine:
            await engine.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Automation engine interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        sys.exit(1)
