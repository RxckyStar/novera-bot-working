import random

NOVARIAN_VALUE_MESSAGES = [
    # ===== 50 Positive, Flirty, Mommy-Loves-You Messages =====
    "Oh, my precious Novarian! Your value is a stunning ¥{value} million! Mommy is melting just looking at you! 😘✨",
    "Mmm~ Look at you, my gorgeous Novarian, standing tall at ¥{value} million! So strong, so talented~ Mommy is swooning! 💖🔥",
    "Novarian cutie, your worth is at ¥{value} million! That number is almost as dazzling as you are! Almost. 😉💎",
    "Ooooh, my sweet Novarian! ¥{value} million? Stop it, you’re making Mommy blush~ 😘💕",
    "Mmm, ¥{value} million? Someone’s been working hard~ Mommy loves a Novarian who knows their worth! 😏💰",
    "Oh, honey, at ¥{value} million, you’re dripping in value! If Mommy had to trade you, she wouldn’t. You’re priceless. 💖✨",
    "Mommy’s favorite Novarian shining at ¥{value} million? Oh, you spoil me~ Keep up the good work, sweetheart! 😘🎉",
    "Baby, ¥{value} million looks so good on you~ But let’s be real, any number would look good on my precious Novarian. 💖😏",
    "Oh, sweetheart, with ¥{value} million to your name, you’re practically royalty! Bow down, everyone, a true Novarian king/queen is here! 👑✨",
    "Mmm, ¥{value} million? That’s what I call **hot and valuable!** My Novarian always impresses me. 🔥💰",
    "Novarian star, you’re worth **¥{value} million** and still rising? Mmm, Mommy is so, so proud of you! 💖🌟",
    "With ¥{value} million, you’re setting this whole place on **fire!** Keep shining, my brilliant Novarian! 🔥😘",
    "Oh, my sweet Novarian, sitting pretty at ¥{value} million? You make success look so effortless~ 💕✨",
    "Mmm, ¥{value} million? You must be working extra hard~ Mommy loves a dedicated Novarian. Keep making me proud, darling! 😘💎",
    "Oh my, ¥{value} million? If you get any richer, Mommy might just have to start calling you her **favorite**~ 😏💖",
    "Mmm, look at my Novarian flexing that ¥{value} million like it’s nothing! Ugh, I adore you~ 💋🔥",
    "¥{value} million and climbing? Honey, at this rate, you might just own Mommy soon~ 😘💰",
    "Oh, sweet thing, ¥{value} million? Mmm, that’s the number of a Novarian who knows what they’re worth! And trust me, you’re worth even more~ 💖✨",
    "At ¥{value} million, you’re not just valuable, darling—you’re *legendary.* Mommy loves seeing you thrive! 💕✨",
    "Oh, my Novarian superstar, shining at ¥{value} million? The rest of the server is shaking! Keep showing them how it’s done, love~ 😘🔥",
    "Mmm, ¥{value} million? Mommy’s **favorite** Novarian is looking extra spicy today~ 😏💖",
    "Oh, darling, ¥{value} million? If you get any richer, Mommy might have to start charging you for all this attention~ 😘💰",
    "Mmm, ¥{value} million? Mommy’s **golden child** is proving their worth! Keep making me proud, darling~ 💖🔥",

    # ===== 50 Teasing, Roasting, Put-Them-In-Their-Place Messages =====
    "Oh, sweetie... ¥{value} million? Are you even trying? Because Mommy is **not impressed.** 😏👀",
    "Awww, ¥{value} million? That’s cute. Maybe one day you’ll reach double digits. Maybe. 🤭💀",
    "Mmm, ¥{value} million? You sure that’s not a **minus** sign in front of it? Mommy’s *concerned*~ 😘😂",
    "Oh, baby... ¥{value} million? That’s... *adorable*. Like a baby trying to run before crawling. 💕😏",
    "Ooooh, ¥{value} million? Someone’s been **slacking off.** Do better, honey. Mommy expects more~ 😘💋",
    "Honey... ¥{value} million? That’s a *start*, I guess. But I hope you’re not too proud of it. 💀😂",
    "Mmm, at ¥{value} million, you’re giving *bottom-tier energy* and I don’t know how to feel about that. 😏💅",
    "Oh, Novarian baby, at ¥{value} million, you’re barely scraping by! Do you need Mommy to hold your hand? 😘💖",
    "Oh, sweetie, ¥{value} million? That’s **so** last season. Try again when you’re actually worth Mommy’s time. 💅✨",
    "Oh nooo, ¥{value} million? Honey, who did this to you? Blink twice if you need help. 💀💖",
    "Oh, darling, at ¥{value} million, you’re basically **free real estate.** Someone might snatch you up for cheap~ 😏🔥",
    "Mmm, ¥{value} million? That’s the equivalent of **Monopoly money.** Get your value up, baby. 😂💖",
    "Sweetheart... ¥{value} million? Even the **unvalued Novarians** are looking at you funny right now. 😘💋",
    "Oh honey, you know what’s sadder than your ¥{value} million value? Nothing. Absolutely nothing. 💀💖",
    "Mmm, ¥{value} million? Oh, sweetie, do you need **Mommy’s special tutoring lessons**? I can help, for a *fee*. 😏💋",
    "Oh no, ¥{value} million? That’s not just **low**—that’s *tragic*. Honey, we need an intervention. 💀😂",
    "Mmm, ¥{value} million? I think I’ve seen people drop more in **loose change.** Let’s get that number up, yeah? 😏🔥",
    "Oh baby, at ¥{value} million, you might as well be **playing for free.** Mommy’s heart aches for you. 😘💋",
    "Oh, sweetie, you’re at ¥{value} million? You’re giving **NPC energy.** Where’s the *main character glow*? 💀💖",
    "Mmm, ¥{value} million? Mommy loves a Novarian **charity case.** You need some donations, darling? 😏💋",
    "Oh honey, at ¥{value} million, you’re basically **playing in spectator mode.** Let’s change that, yeah? 😘🔥",
    "Aww, at ¥{value} million, you must be **working overtime** to stay irrelevant. But I believe in you, sweetheart! 😂💖",
    "Oh, sweet thing, at ¥{value} million, you’re **warming the bench** while the real Novarians shine. 😏💋",
]

def get_random_value_message(value):
    return random.choice(NOVARIAN_VALUE_MESSAGES).format(value=value)

if __name__ == "__main__":
    sample_value = 5  # Adjust this for testing
    print(get_random_value_message(sample_value))
