#!/usr/bin/env python3
"""Check URLs and deploy if successful."""
import sys
import argparse
import logging
import signal
from contextlib import contextmanager
import time
from multi_monitor import check_urls, deploy

class TimeoutException(Exception):
    pass

@contextmanager
def timeout(seconds):
    def signal_handler(signum, frame):
        raise TimeoutException("Timed out!")
    
    # Register a function to raise a TimeoutException on the signal
    signal.signal(signal.SIGALRM, signal_handler)
    signal.alarm(seconds)
    
    try:
        yield
    finally:
        # Disable the alarm
        signal.alarm(0)

def main():
    parser = argparse.ArgumentParser(description='Check URLs and deploy if successful')
    parser.add_argument('--timeout', type=int, default=300,
                      help='Timeout in seconds (default: 300)')
    parser.add_argument('--verbose', action='store_true',
                      help='Enable verbose logging')
    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    try:
        with timeout(args.timeout):
            # Run the check
            logging.info(f"Starting URL checks with {args.timeout}s timeout...")
            start_time = time.time()
            
            # Run the check command
            check_result = check_urls(verbose=args.verbose)
            if not check_result:
                logging.error("URL checks failed")
                sys.exit(1)
            
            # If checks pass, run deploy
            logging.info("URL checks passed, deploying...")
            deploy_result = deploy()
            if not deploy_result:
                logging.error("Deploy failed")
                sys.exit(1)
            
            elapsed = time.time() - start_time
            logging.info(f"Check and deploy completed successfully in {elapsed:.1f}s")
            
    except TimeoutException:
        logging.error(f"Process timed out after {args.timeout} seconds")
        sys.exit(1)
    except KeyboardInterrupt:
        logging.info("\nProcess interrupted by user")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()
