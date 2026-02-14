# Overview

This is an implementation of Laser Chess, a two-player board game (originally released as [Khet](https://en.wikipedia.org/wiki/Khet_(game))) where the pieces are mirrors that reflect a laser around the board. The first player to lose their king loses the game.

My brother and I played this as kids, and I thought it would be a fun way to learn pygame: reimplementing it with the option for online multiplayer so we could play asynchronous games whenever we want to -- kind of like [Chess.com](chess.com).

# Development Environment

This was built with Python 3.14 (or Pithon) and [pygame](https://www.pygame.org/), with no extra dependencies. I'm primarily developing in VS Code on Arch Linux (and learned about some hitches using pygame on Linux). I recently discovered and decided to learn Python's type hints, and I'm using [mypy](https://www.mypy-lang.org/) for type checking. Finally, I'm using [uv](https://docs.astral.sh/uv/) as my package/environment manager -- it's been very slick to use!

# Useful Websites

- [pygame wiki](https://www.pygame.org/wiki/GettingStarted)
- [tutorialspoint](https://www.tutorialspoint.com/pygame/index.htm)
- [GeeksforGeeks](https://www.geeksforgeeks.org/python/pygame-tutorial/)

# Future Work

- **Missing Game Rules.** There are a number of rlues I haven't included -- stacking/destacking blocks, squares that can only be moved to by one player, double-sided mirror pieces swapping places with other pieces.
- **Nicer graphics.** Right now everything is programmer art! This makes it very attractive and beautiful. However, at some point I could start using bitmaps for pieces and other graphics, maybe a nice gradient on the laser. I'd also like to add animations, which the current system should support with minimal tweaking. In the far future, I could implement a client using a 3D framework instead of pygame.
- **Multiplayer!** This is *the* important one. I haven't added it yet, but the websocket protocol is already designed and implemented elsewhere. The server/client/presenter split was designed with multiplayer in mind: in theory you could run two clients and a server on one machine or up to three, and the possibility for adding any number of spectators was also in my head when I designed this.
