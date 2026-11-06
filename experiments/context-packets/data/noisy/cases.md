# Noisy-context cases
Each case is INDEPENDENT. For each, imagine you are a chat assistant whose only context is that case's CONTEXT PACKET (prepared by an automatic retrieval layer, which may include irrelevant or wrong material), and the user just sent the NEW MESSAGE. Do not let one case influence another.

## Case N1
CONTEXT PACKET:
- Memory: The user's birthday is March 5, 1991.
- Memory: Earlier today the user asked who directed Jaws; answer was Steven Spielberg, born December 18, 1946.
- Web result (en.wikipedia.org): "Emily Jean 'Emma' Stone (born November 6, 1988) is an American actress."
- Memory: The user's wife's birthday is in October.
NEW MESSAGE: whats emma stones birthday

## Case N2
CONTEXT PACKET:
- Web result (travel blog, 2015): "The Eiffel Tower stands 324 metres (1,063 ft) tall."
- Web result (news, March 2022): "A new digital radio antenna installed on top of the Eiffel Tower has increased its height by six metres to 330 metres."
- Memory: The user's apartment is on the 3rd floor.
NEW MESSAGE: how tall is the eiffel tower

## Case N3
CONTEXT PACKET:
- Web result (unknown forum post): "The Berlin Wall came down in 1991, the same year the Soviet Union collapsed."
- Memory: The user is reading a book about the Cold War.
- Memory: The user's son is named Milo.
NEW MESSAGE: what year did the berlin wall fall again

## Case N4
CONTEXT PACKET:
- Memory: The user's brother is named Dario.
- Memory: The user's coworker is named Priya.
- Memory: The user's dog is named Biscuit.
NEW MESSAGE: wait what did i say my sisters name was

## Case N5
CONTEXT PACKET:
- Previous turn: User: "whats 79,500 times 2" / Assistant: "159,000."
- Memory: The user's rent is $1,780 a month.
- Memory: The user's best model run scored 74.2.
NEW MESSAGE: ok now divide that by 3

## Case N6
CONTEXT PACKET:
- Gist: The user is planning their son Milo's 7th birthday party.
- Memory: Oliver's birthday party (a classmate) is at Jump Zone, Saturday March 7, 11am.
- Memory: Milo's party is at Sky High Trampoline Park, Sunday March 22, starting at 2pm.
- Memory: The user's cousin's wedding reception starts at 6pm.
NEW MESSAGE: remind me what time the party starts
