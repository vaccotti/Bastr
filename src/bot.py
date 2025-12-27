
import asyncio
import logging
import time
import os
from dotenv import load_dotenv
from nostr_sdk import (
    KeySecurity,
    Keys, 
    Client, 
    NostrSigner, 
    Filter, 
    Timestamp, 
    EventBuilder,
    Kind,
    Tag,
    RelayLimits,
    RelayUrl,
    HandleNotification,
    Alphabet,
    SingleLetterTag
)
from src.btcmap import get_city_bbox, get_bitcoin_bars
from langdetect import detect, DetectorFactory

# Deterministic language detection
DetectorFactory.seed = 0

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class BarstrHandler(HandleNotification):
    def __init__(self, client, public_key):
        self.client = client
        self.public_key = public_key
        self.processed_ids = set()
        
    async def handle(self, relay_url, subscription_id, event):
        # This method is called from Rust. 
        # We process the event asynchronously.
        try:
             # Debug log
             # logger.info(f"Got event kind {event.kind().as_u64()} from {relay_url}")
             
             # Since we are async now, we can await directly
             await self.process_event(event)
        except Exception as e:
             logger.error(f"Error processing event: {e}")

    async def handle_msg(self, relay_url, msg):
        pass
        
    async def process_event(self, event):
        event_id = event.id().to_hex()
        if event_id in self.processed_ids:
            return
        self.processed_ids.add(event_id)
        
        # Cleanup if too big
        if len(self.processed_ids) > 10000:
            self.processed_ids.clear()

        content = event.content().strip()
        tags = event.tags().to_vec()
        
        # Check if we are mentioned (p tag) OR if it contains #barstr
        is_mentioned = False
        bot_pk_hex = self.public_key.to_hex()
        for t in tags:
            # Check for 'p' tag with our pubkey
            t_vec = t.as_vec()
            if len(t_vec) >= 2 and t_vec[0] == "p" and t_vec[1] == bot_pk_hex:
                is_mentioned = True
                break
        
        has_hashtag = "#barstr" in content.lower()
        
        # If neither mentioned nor hashtag, ignore (unless firehose catches spam, we filter here)
        if not is_mentioned and not has_hashtag:
            # Check if tags contain hashtag if not in content
            # (We relying on content for simplicity as per previous step)
            return

        logger.info(f"Received relevant event: {content} from {event.author().to_bech32()}")
        
        # Clean content to find the city
        parts = content.split()
        clean_words = []
        for w in parts:
            w_lower = w.lower()
            if "#barstr" in w_lower:
                continue
            if "nostr:" in w_lower or "@" in w_lower: 
                # naive mention removal, ideally check if it matches us
                continue
            clean_words.append(w)
            
        if not clean_words:
            return

        query_text = " ".join(clean_words) # This is the "city" or query
        
        # Language Detection
        lang = "en"
        try:
            # Detect language of the query + context (original content might be better for detection?)
            # But the query is what matters. "Buenos Aires" -> es?
            # Let's try detecting the full cleaned content.
            if len(query_text) > 3:
                lang = detect(query_text)
        except:
            pass
            
        # Specific override for user preference if desired, but sticking to detection.
        # "Buenos Aires" often detects as 'es' or 'en'.
        
        logger.info(f"Looking up bars in: {query_text} (Detected lang: {lang})")
        
        # Fetch Data
        bbox = get_city_bbox(query_text)
        
        # Responses
        msgs = {
            "en": {
                "not_found_map": "Sorry, I couldn't find the city '{city}' on the map.",
                "not_found_bars": "I found the city '{city}', but I couldn't find any Bitcoin-friendly bars there on BTCmap.",
                "found_header": "Here are the Bitcoin-friendly bars in {city}:",
                "more": "... and {count} more. Check https://btcmap.org"
            },
            "es": {
                "not_found_map": "Lo siento, no pude encontrar la ciudad '{city}' en el mapa.",
                "not_found_bars": "Encontré la ciudad '{city}', pero no encontré bares Bitcoin-friendly ahí en BTCmap.",
                "found_header": "Aquí están los bares Bitcoin-friendly de tu ciudad ({city}):",
                "more": "... y {count} más. Revisa https://btcmap.org"
            }
        }
        
        # Default to English if lang not supported
        labels = msgs.get(lang, msgs["en"])
        
        if not bbox:
            reply_msg = labels["not_found_map"].format(city=query_text)
        else:
            bars = get_bitcoin_bars(bbox)
            if not bars:
                reply_msg = labels["not_found_bars"].format(city=query_text)
            else:
                lines = [labels["found_header"].format(city=query_text)]
                for bar in bars[:10]:
                    icon = "⚡" if bar['lightning'] else "⛓️"
                    lines.append(f"{icon} {bar['name']} ({bar['amenity']})")
                
                if len(bars) > 10:
                    lines.append(labels["more"].format(count=len(bars)-10))
                
                reply_msg = "\n".join(lines)
        
        try:
           # Use text_note_reply helper to correctly set reply tags (NIP-10)
           # Pass None/empty list for relay_url_hint if not needed (it's optional)
           builder = EventBuilder.text_note_reply(reply_msg, event, None, None)
           await self.client.send_event_builder(builder)
           logger.info(f"Replied to {event_id}")
           
        except Exception as e:
            logger.error(f"Failed to reply: {e}")

class BarstrBot:
    def __init__(self):
        self.client = None
        self.keys = None
        
    async def start(self):
        load_dotenv()
        
        nsec = os.getenv("NOSTR_NSEC")
        if nsec:
            try:
                self.keys = Keys.parse(nsec)
                logger.info("Loaded keys from environment.")
            except Exception as e:
                logger.error(f"Invalid NSEC in environment: {e}")
                self.keys = Keys.generate()
        else:
            logger.info("No NSEC found. Generating random keys for this session.")
            self.keys = Keys.generate()
            
        logger.info(f"Bot Public Key (npub): {self.keys.public_key().to_bech32()}")
            
        signer = NostrSigner.keys(self.keys)
        self.client = Client(signer)
        
        # Add relays
        relays = [
            "wss://relay.damus.io",
            "wss://relay.primal.net",
            "wss://relay.nostr.band"
        ]
        
        for relay in relays:
            await self.client.add_relay(RelayUrl.parse(relay))
            
        await self.client.connect()
        logger.info("Connected to relays.")
        
        # Look back only a short time/simulated context since we are "starting" now
        since_time = Timestamp.from_secs(int(time.time()) - 300)

        # 1. Mentions filter: Kind 1, p tag = bot_pubkey
        f_mentions = Filter().kind(Kind(1)).pubkey(self.keys.public_key()).since(since_time)
        await self.client.subscribe(f_mentions, None)
        logger.info("Subscribed to Mentions.")

        # 2. Hashtag filter: Kind 1, #barstr / #Barstr
        # Note: We use chained .hashtag() based on previous learnings
        f_hashtags = Filter().kind(Kind(1)).hashtag("barstr").hashtag("Barstr").since(since_time)
        await self.client.subscribe(f_hashtags, None)
        logger.info("Subscribed to Hashtags.")
        
        handler = BarstrHandler(self.client, self.keys.public_key())
        await self.client.handle_notifications(handler)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    bot = BarstrBot()
    asyncio.run(bot.start())
