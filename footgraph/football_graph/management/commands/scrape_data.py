from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from django.core.management.base import BaseCommand
from football_graph.models import League, Club, Player, Data
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(threadName)s - %(message)s')
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Scrape fotmob data using Selenium with multi-threading'

    def add_arguments(self, parser):
        parser.add_argument(
            '--max-workers',
            type=int,
            default=3,
            help='Maximum number of worker threads (default: 3)'
        )

    def handle(self, *args, **kwargs):
        max_workers = kwargs.get('max_workers', 3)
        
        urls = [
            'https://www.fotmob.com/leagues/53/overview/ligue-1',
            'https://www.fotmob.com/leagues/47/overview/premier-league',
            'https://www.fotmob.com/leagues/87/overview/laliga',
            'https://www.fotmob.com/leagues/54/overview/bundesliga',
            'https://www.fotmob.com/leagues/55/overview/serie-a',
        ]
        
        driver = create_driver()
        try:
            all_team_links = get_squad_links(driver, urls)
            logger.info(f"Found {len(all_team_links)} team links")
        finally:
            driver.quit()

        if not all_team_links:
            logger.error("No team links found, exiting")
            return

        all_player_links = get_player_links_multithreaded(all_team_links, max_workers)
        logger.info(f"Found {len(all_player_links)} player links")

        if not all_player_links:
            logger.error("No player links found, exiting")
            return

        get_player_data_multithreaded(all_player_links, max_workers)

def create_driver():
    """Crée une instance de WebDriver avec les options appropriées"""
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    return webdriver.Chrome(service=Service(), options=options)

def get_squad_links(driver, urls):
    """Version originale pour récupérer les liens d'équipes"""
    logger.info("Starting to scrape team links...")
    try:
        all_team_links = []
        for url in urls:
            driver.get(url)
            driver.implicitly_wait(5)

            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "TableContainer"))
            )
            table_container = driver.find_element(By.CLASS_NAME, "TableContainer")
            links = table_container.find_elements(By.TAG_NAME, "a")
            league_title_element = driver.find_element(By.CLASS_NAME, "css-4ow769-TeamOrLeagueName")
            league_title = get_text_or_none(league_title_element)

            for link in links:
                href = link.get_attribute("href")
                if href and href.startswith("https://www.fotmob.com/teams/"):
                    team_link = href.replace("overview", "squad")
                    try:
                        team_name = get_text_or_none(link.find_element(By.CLASS_NAME, "TeamName"))
                    except:
                        team_name = "Unknown Team"

                    league, created = League.objects.get_or_create(name=league_title)
                    club, created = Club.objects.get_or_create(
                        name=team_name,
                        league=league
                    )

                    all_team_links.append(team_link)

        logger.info(f"Found {len(all_team_links)} team links.")
        return all_team_links
    except Exception as e:
        logger.error(f"Error while scraping team links: {str(e)}")
        return []

def scrape_team_players(team_link):
    """Scrape les joueurs d'une équipe (fonction pour thread)"""
    driver = create_driver()
    try:
        logger.info(f"Scraping team: {team_link}")
        driver.get(team_link)
        driver.implicitly_wait(5)

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "css-9pqpod-SquadPlayerLink"))
        )
        player_links = driver.find_elements(By.CLASS_NAME, "css-9pqpod-SquadPlayerLink")
        
        team_player_links = []
        for player_link in player_links:
            href = player_link.get_attribute("href")
            if href and href.startswith("https://www.fotmob.com/players/"):
                team_player_links.append(href)
        
        logger.info(f"Found {len(team_player_links)} players for team")
        return team_player_links

    except Exception as e:
        logger.error(f"Error scraping team {team_link}: {e}")
        return []
    finally:
        driver.quit()

def get_player_links_multithreaded(team_links, max_workers=3):
    """Version multi-thread pour récupérer les liens de joueurs"""
    logger.info(f"Starting to scrape player links with {max_workers} workers...")
    all_player_links = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_team = {executor.submit(scrape_team_players, team_link): team_link 
                         for team_link in team_links}
        
        for future in as_completed(future_to_team):
            team_link = future_to_team[future]
            try:
                player_links = future.result()
                all_player_links.extend(player_links)
            except Exception as e:
                logger.error(f"Error processing team {team_link}: {e}")
    
    return all_player_links

def scrape_single_player(player_link, index, total):
    """Scrape un seul joueur (fonction pour thread)"""
    driver = create_driver()
    try:
        return scrape_player_with_driver(driver, player_link, index, total)
    finally:
        driver.quit()

def scrape_player_with_driver(driver, player_link, index, total):
    """Version modifiée de get_player_data pour un seul joueur"""
    data_match_dict = {
        'goals': 'Goals',
        'expected_goals': 'Expected goals (xG)',
        'xg_on_target': 'xG on target (xGOT)',
        'penalty_goals': 'Penalty goals',
        'non_penalty_xg': 'Non-penalty xG',
        'shots': 'Shots',
        'shots_on_target': 'Shots on target',
        'assists': 'Assists',
        'expected_assists': 'Expected assists (xA)',
        'successful_passes': 'Successful passes',
        'pass_accuracy': 'Pass accuracy',
        'accurate_long_balls': 'Accurate long balls',
        'long_ball_accuracy': 'Long ball accuracy',
        'chances_created': 'Chances created',
        'successful_crosses': 'Successful crosses',
        'cross_accuracy': 'Cross accuracy',
        'successful_dribbles': 'Successful dribbles',
        'dribble_success': 'Dribble success',
        'touches': 'Touches',
        'touches_in_opposition_box': 'Touches in opposition box',
        'dispossessed': 'Dispossessed',
        'fouls_won': 'Fouls won',
        'penalties_awarded': 'Penalties awarded',
        'tackles_won': 'Tackles won',
        'tackles_won_percentage': 'Tackles won %',
        'duels_won': 'Duels won',
        'duels_won_percentage': 'Duels won %',
        'aerial_duels_won': 'Aerial duels won',
        'aerial_duels_won_percentage': 'Aerial duels won %',
        'interceptions': 'Interceptions',
        'blocked': 'Blocked',
        'fouls_committed': 'Fouls committed',
        'recoveries': 'Recoveries',
        'possession_won_final_3rd': 'Possession won final 3rd',
        'dribbled_past': 'Dribbled past',
        'yellow_cards': 'Yellow cards',
        'red_cards': 'Red cards',
        'saves': 'Saves',
        'save_percentage': 'Save percentage',
        'goals_conceded': 'Goals conceded',
        'goals_prevented': 'Goals prevented',
        'clean_sheets': 'Clean sheets',
        'error_led_to_goal': 'Error led to goal',
        'high_claim': 'High claim',
        'gk_pass_accuracy': 'Pass accuracy',
        'gk_accurate_long_balls': 'Accurate long balls',
        'gk_long_ball_accuracy': 'Long ball accuracy',
    }

    player_slug = player_link.rsplit('/', 1)[-1]
    logger.info(f"Processing player {index}/{total}: {player_slug}")
    
    try:
        driver.get(player_link)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "css-zt63wq-PlayerNameCSS"))
        )

        name = get_text_or_none(driver.find_element(By.CLASS_NAME, "css-zt63wq-PlayerNameCSS"))
        club_name = get_text_or_none(driver.find_element(By.CLASS_NAME, "css-14k6s2u-TeamCSS"))
        if club_name.endswith('(on loan)'):
            club_name = club_name[:-len(' (on loan)')].strip()
        
        positions = driver.find_elements(By.CLASS_NAME, "css-1g41csj-PositionsCSS")
        positions_text = ', '.join([get_text_or_none(pos) for pos in positions])

        stat_fields = driver.find_elements(By.XPATH, "//*[contains(@class, 'PlayerBioStatCSS')]")
        player_data = {
            'height': None,
            'shirt_number': None,
            'age': None,
            'foot': None,
            'country': None,
            'market_value': None,
        }
        
        for field in stat_fields:
            try:
                title = get_text_or_none(field.find_element(By.CLASS_NAME, "css-10h4hmz-StatTitleCSS"))
                value = get_text_or_none(field.find_element(By.CLASS_NAME, "css-to3w1c-StatValueCSS"))

                if title == "Height":
                    player_data['height'] = int(value.split()[0]) if value.split()[0].isdigit() else None
                elif title == "Shirt":
                    player_data['shirt_number'] = value
                elif title == "Preferred foot":
                    player_data['foot'] = value
                elif title == "Country":
                    player_data['country'] = value
                elif title == "Market value":
                    player_data['market_value'] = parse_market_value(value)
                elif "years" in value:
                    player_data['age'] = int(value.split()[0]) if value.split()[0].isdigit() else None
            except Exception as e:
                logger.warning(f"Error parsing stat field: {e}")

        fotmob_id = player_link.split('/')[-2]

        # lock pour les opérations de base de données
        with db_lock:
            try:
                club = Club.objects.get(name=club_name)
            except Club.DoesNotExist:
                logger.info(f"{club_name} not found.")

            player, _ = Player.objects.update_or_create(
                fotmob_id=fotmob_id,
                defaults={
                    'name': name,
                    'club': club,
                    'position': positions_text,
                    'country': player_data.get('country'),
                    'shirt_number': int(player_data['shirt_number']) if player_data.get('shirt_number') and player_data['shirt_number'].isdigit() else None,
                    'age': player_data.get('age'),
                    'height': player_data.get('height'),
                    'market_value': player_data.get('market_value'),
                }
            )

        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CLASS_NAME, "css-1v73fp6-StatItemCSS"))
            )
            stat_items = driver.find_elements(By.CLASS_NAME, "css-1v73fp6-StatItemCSS")
            stats_data = {}
            for item in stat_items:
                title = get_text_or_none(item.find_element(By.CLASS_NAME, "css-2duihq-StatTitle"))
                value = get_text_or_none(item.find_element(By.CLASS_NAME, "css-jb6lgd-StatValue"))
                for key, label in data_match_dict.items():
                    if title == label:
                        stats_data[key] = parse_stat_value(value)
            
            with db_lock:
                Data.objects.update_or_create(player=player, defaults=stats_data)
            
            logger.info(f"\033[92m{name} scraped and updated.\033[0m")
            return True
        except:
            logger.info(f"\033[93mNo stats available for {name}.\033[0m")
            return True

    except Exception as e:
        logger.error(f"\033[91mError for player {player_slug}: {e}\033[0m")
        return False

db_lock = threading.Lock()

def get_player_data_multithreaded(player_links, max_workers=3):
    """Version multi-thread pour scraper les données des joueurs"""
    logger.info(f"Starting to scrape player data with {max_workers} workers...")
    successful_count = 0
    failed_count = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_player = {
            executor.submit(scrape_single_player, link, i+1, len(player_links)): link 
            for i, link in enumerate(player_links)
        }
        
        for future in as_completed(future_to_player):
            player_link = future_to_player[future]
            try:
                success = future.result()
                if success:
                    successful_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                logger.error(f"Error processing player {player_link}: {e}")
                failed_count += 1
    
    logger.info(f"\033[92mSuccess: {successful_count}, Failed: {failed_count}\033[0m")

def get_text_or_none(element):
    try:
        return element.text.strip()
    except:
        return None

def parse_stat_value(value):
    if value.endswith('%'):
        value = value[:-1]
    value = value.replace(',', '.')
    try:
        value = float(value) if '.' in value else int(value)
        return value
    except:
        return None

def parse_market_value(value):
    value = value.replace('€', '').strip().upper()
    if value.endswith('M'):
        return int(float(value[:-1]) * 1_000_000)
    elif value.endswith('K'):
        return int(float(value[:-1]) * 1_000)
    else:
        try:
            return int(value)
        except:
            return None