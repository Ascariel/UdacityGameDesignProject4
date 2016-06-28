# -*- coding: utf-8 -*-`
"""api.py - Create and configure the Game API exposing the resources.
This can also contain game logic. For more complex games it would be wise to
move game logic to another file. Ideally the API will be simple, concerned
primarily with communication to/from the API's users."""

import sys
import logging
import endpoints
import time
from protorpc import remote, messages
from protorpc import message_types

from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.ext import ndb

from models import User, Game, Score, Move
from models import StringMessage, NewGameForm, GameForm, MakeMoveForm,\
    ScoreForms
from utils import get_by_urlsafe

# NEW_GAME_REQUEST = endpoints.ResourceContainer(NewGameForm)
# GET_GAME_REQUEST = endpoints.ResourceContainer(
#         urlsafe_game_key=messages.StringField(1),)
# MAKE_MOVE_REQUEST = endpoints.ResourceContainer(
#     MakeMoveForm,
#     urlsafe_game_key=messages.StringField(1),)

# USER_REQUEST = endpoints.ResourceContainer(user_name=messages.StringField(1),
#                                            email=messages.StringField(2))

START_GAME = endpoints.ResourceContainer(game_id = messages.StringField(1), 
                                         player1=messages.StringField(2), player2=messages.StringField(3))

GAME_ID = endpoints.ResourceContainer(game_id = messages.StringField(1))

MAKE_NEXT_MOVE_REQUEST = endpoints.ResourceContainer(
     x = messages.IntegerField(1), y = messages.IntegerField(2),
      user_id=messages.StringField(3), game_id=messages.StringField(4))

MEMCACHE_MOVES_REMAINING = 'MOVES_REMAINING'

@endpoints.api(name='guess_a_number', version='v1')
class GuessANumberApi(remote.Service):
    """Game API"""



    @endpoints.method(request_message=START_GAME,
                      response_message=StringMessage,
                      path='start_game',
                      name='start_game',
                      http_method='POST')

    def startGame(self, request):
      """ Initializes all 9 posible moves using provided game_id """

      game_id = request.game_id
      player1 = request.player1
      player2 = request.player2

      if request.game_id == None:
        return StringMessage(message = "Failed, Empty game_id. Please enter a valid unique game_id")

      if request.player1 == None or request.player2 == None:
        return StringMessage(message = "Failed, Missing Players. Make sure both player ids are present")        

      if request.player1 == request.player2:
        return StringMessage(message = "Failed, Player Ids must be different")                

      

      game_exists = len(Move.query(Move.game_id == game_id).fetch()) > 0
      if game_exists:
        return StringMessage(message = "Game Creation Failed, Game ID already exists: {0}".format( game_id ) )

      # Creating Game
      game = Game(game_id = game_id, player1 = request.player1, player2 = request.player2)
      game.put()

      print("New Game Created: {0}".format(game))        

      mv1 = Move(x = 0, y = 0, game_id = game_id, available = True, description = "[0,0]")
      mv2 = Move(x = 0, y = 1, game_id = game_id, available = True, description = "[0,1]")
      mv3 = Move(x = 0, y = 2, game_id = game_id, available = True, description = "[0,2]")

      mv4 = Move(x = 1, y = 0, game_id = game_id, available = True, description = "[1,0]")
      mv5 = Move(x = 1, y = 1, game_id = game_id, available = True, description = "[1,1]")
      mv6 = Move(x = 1, y = 2, game_id = game_id, available = True, description = "[1,2]")

      mv7 = Move(x = 2, y = 0, game_id = game_id, available = True, description = "[2,0]")
      mv8 = Move(x = 2, y = 1, game_id = game_id, available = True, description = "[2,1]")
      mv9 = Move(x = 2, y = 2, game_id = game_id, available = True, description = "[2,2]")

      # ndb.put_multi([ mv1, mv2, mv3, mv4, mv5, mv6, mv7, mv8, mv9])

      for m in [ mv1, mv2, mv3, mv4, mv5, mv6, mv7, mv8, mv9]:
        print(" saving: {0}".format(m) )
        m.put()

      return StringMessage(message = "New Game Created, ID: {0} | Player 1: {1} | Player 2: {2}".format( game_id, player1, player2 ) )


    @endpoints.method(request_message = GAME_ID, response_message = StringMessage,
                      path = "game_reset", name = "game_reset", http_method = "POST")
    def resetGameState(self, request):
      # Remove move ownership for all users
      # Resets move availablities to True
      game_id = request.game_id

      # for the moment, resets every move for provided game_id
      moves = Move.query().fetch()
      moves_deleted = Move.query(Move.game_id == game_id).fetch()


      game = Game.query(Game.game_id == game_id).get()

      if game == None:
        return StringMessage(message = "No Game found for ID:  {0} ".format(game_id))

      print("game id is {0} {1}".format(game_id, moves[0].game_id ))

      # Deleting Game
      game.key.delete()

      # Deleting Moves
      for move in moves_deleted:
        print("Deleting moves, {0}".format(move))
        move.key.delete()

      return StringMessage(message = "Game Reset Complete, deleted {0} moves for Game:  {1} ".format(len(moves_deleted), game_id))


    @endpoints.method(request_message= MAKE_NEXT_MOVE_REQUEST, response_message = StringMessage,
                      name = "make_move", path="make_move", http_method="POST" )
    def makeMove(self, request):
      """ Asigns specific move to a user for a specific game_id, as long as its available """
      x = request.x   
      y = request.y
      game_id = request.game_id
      user_id = request.user_id

      game = Game.query(Game.game_id == game_id).get()
      queried_move = Move.query(Move.x == x, Move.y == y, 
                        Move.game_id == game_id).fetch(1)

      if game == None :
        print("\n\nInvalid Move, Wrong Game ID\n\n")
        return StringMessage(message = "Invalid Move, Wrong Game ID" )
 
      winner_id = GuessANumberApi._check_winning_condition(game_id) 

      if winner_id != False:
        print("\n\n Game Won By {0} \n\n".format(winner_id))
        return StringMessage(message = "\n\n Game Won By {0} \n\n".format(winner_id))             

      available_moves = Move.query(Move.available == True, Move.game_id == game_id).fetch()
      
      if len(available_moves) == 0:
        print("\n\n Game Ended, No more moves left {0} \n\n".format(game_id))
        return "no_more_moves"        

      if user_id == None or user_id not in [game.player1, game.player2]:
        print("\n\nInvalid move parameters\n\n")
        return StringMessage(message = "Invalid Move, Wrong User ID" )

      if len(queried_move) == 0:
        print("\n\nInvalid move parameters\n\n")
        return StringMessage(message = "Invalid move parameters, Wrong Game ID or Move out of range" )

      if user_id == game.last_play_user_id:
        print("\n\n This Player already moved\n\n")
        return StringMessage(message = "Invalid move, This Player already moved" )        

      move = queried_move[0]
      if move.available != True:
        print("\n\nMove already done by: {0} \n\n".format(move.user_id))
        return StringMessage(message = "Move {0} has already been made by User with ID: : {1}"
                             .format(move.description, move.user_id) )        

      move.user_id = user_id
      move.available = False
      move.put()

      game.last_play_user_id = user_id
      game.put()

      GuessANumberApi._show_game_picture(game_id)
      GuessANumberApi._check_game_state(game_id)

      return StringMessage(message = "Move {0} assign to {1} for game_id: {2}, x:{3} and y:{4}".format(move.description, user_id, game_id, x, y) )

    @endpoints.method(request_message = GAME_ID, response_message = StringMessage,
                      path = "check_game_state", name = "check_game_state", http_method = "POST")
    def checkGameState(self, request):
      game_id = request.game_id
      game = Game.query(Game.game_id == game_id).get()

      if game == None:
        print("\n\n Game doesnt exist for ID: {0} \n\n".format(game_id))
        return StringMessage(message = "Game doesnt exist for ID: {0} "
                             .format(game_id) )  

      state = GuessANumberApi._check_game_state(game_id)   
      
      if state == "no_more_moves":
        print("\n\n Game Ended, No Winners: {0} \n\n".format(game_id))
        return StringMessage(message = "Game Ended, No Winners: {0} "
                             .format(game_id) )  

      if state == "no_winners_yet":
        print("\n\n No Winners Yet, Game Continues: {0} \n\n".format(game_id))
        return StringMessage(message = "No Winners Yet, Game Continues: {0} "
                             .format(game_id) )  
        


      print("\n\n Game Won By: {0} \n\n".format(state))
      return StringMessage(message = "Game Won By: {0} "
                           .format(state) )  
        

    @endpoints.method(message_types.VoidMessage, response_message = StringMessage,
                      path="show_game_ids", name="show_game_ids", http_method='GET')
    def show_game_ids(self, request):

      moves = Move.query().fetch()
      game_ids = []

      for move in moves:
        game_id = move.game_id

        if game_id not in game_ids:
          game_ids.append(game_id)

          #Showing game moves per game
          GuessANumberApi._show_game_picture(game_id)
          GuessANumberApi._check_game_state(game_id)          


      print( "\n\n Total Game IDS: {0}, IDS: {1} \n\n".format( len(game_ids), str(game_ids) ) ) 
      return StringMessage(message=  "Total Moves: {0}, Total Game IDS: {1}, IDS: {2}".format( len(moves), len(game_ids), str(game_ids) ) )


    # @endpoints.method(request_message = START_GAME, response_message = StringMessage)
    @staticmethod
    def _show_game_picture(game_id):

      """ Print visual representation of game state """

      moves = Move.query(Move.game_id == game_id).order(Move.x, Move.y).fetch()

      if len(moves) == 0:
        print("\n\nCant print game state, Invalid game_id {0}\n\n".format(game_id))
        return StringMessage(message = "Invalid move parameters. no game found" )

      player1,player2 = GuessANumberApi._get_players_in_game(game_id)

      print("Current Players for Game ID {0}: {1}, {2}".format(game_id, player1, player2) )


      m_00 = Move.query(Move.x == 0, Move.y == 0, 
                        Move.game_id == game_id).fetch(1)[0]
      m_01 = Move.query(Move.x == 0, Move.y == 1, 
                        Move.game_id == game_id).fetch(1)[0] 
      m_02 = Move.query(Move.x == 0, Move.y == 2, 
                        Move.game_id == game_id).fetch(1)[0] 
      m_10 = Move.query(Move.x == 1, Move.y == 0, 
                        Move.game_id == game_id).fetch(1)[0] 
      m_11 = Move.query(Move.x == 1, Move.y == 1, 
                        Move.game_id == game_id).fetch(1)[0] 
      m_12 = Move.query(Move.x == 1, Move.y == 2, 
                        Move.game_id == game_id).fetch(1)[0] 
      m_20 = Move.query(Move.x == 2, Move.y == 0, 
                        Move.game_id == game_id).fetch(1)[0] 
      m_21 = Move.query(Move.x == 2, Move.y == 1, 
                        Move.game_id == game_id).fetch(1)[0] 
      m_22 = Move.query(Move.x == 2, Move.y == 2, 
                        Move.game_id == game_id).fetch(1)[0] 

      m_00 = m_00.user_id or m_00.description
      m_01 = m_01.user_id or m_01.description
      m_02 = m_02.user_id or m_02.description
      m_10 = m_10.user_id or m_10.description
      m_11 = m_11.user_id or m_11.description
      m_12 = m_12.user_id or m_12.description
      m_20 = m_20.user_id or m_20.description
      m_21 = m_21.user_id or m_21.description
      m_22 = m_22.user_id or m_22.description

      print("\n\n\n")
      print("TIC TAC TOE GAME")
      print("\n")
      print(" {0} | {1} | {2} ".format(m_00, m_01, m_02))
      print("-----------------------------")
      print(" {0} | {1} | {2} ".format(m_10, m_11, m_12))
      print("-----------------------------")
      print(" {0} | {1} | {2} ".format(m_20, m_21, m_22))
      print("\n\n\n")

    @staticmethod
    def _check_game_state(game_id):
      """ Checks whether there's a victory condition, losing condition, or no more available moves """

      print("\n\nInside check game state, game_id: " + game_id)

      moves = Move.query(Move.game_id == game_id).fetch()
      available_moves = Move.query(Move.available == True, Move.game_id == game_id).fetch()
      
      if len(moves) == 0:
        print("\n\n game_id not found {0} \n\n".format(game_id))
        return "game_id_not_found"

      winner_id = GuessANumberApi._check_winning_condition(game_id)

      if winner_id != False:
        print("\n\n############### Game won by:" + winner_id + " ###############\n\n") 
        return winner_id        

      if len(available_moves) == 0:
        print("\n\n Game Ended, No more moves left {0} \n\n".format(game_id))
        return "no_more_moves"

           
      print("\n\nNo winners yet for game: {0} \n\n".format(game_id))
      return "no_winners_yet"

      

      

    @staticmethod
    def _check_winning_condition(game_id):
      """ Checks whether there's a victory condition and returns winner user_id if there is, else false"""

      # Find game with only 2 allowed users, to be done...
      moves = Move.query(Move.game_id == game_id).fetch()
      user_ids = GuessANumberApi._get_players_in_game(game_id)

      if len(moves) == 0:
        print("\n\n game_id not found {0} \n\n".format(game_id))
        return False
        return "game_id not found"
      if None in user_ids:
        print("\n\n not all users have played a move: {0} \n\n".format(user_ids))
        return False
        return "not all users have played a move"

      print("\n\nChecking winning condition for game id: " + game_id)

      user_1 = user_ids[0]
      user_2 = user_ids[1]

      for i in range(0,3):

        # Checking for Horizontal Wins
        horizontal_moves = Move.query(Move.game_id == game_id, Move.x == i) 
        horizontal_moves = [h.user_id for h in horizontal_moves]

        unique_owner = list( set(horizontal_moves) ) 

        if None not in unique_owner and len(unique_owner) == 1:
          winner_id = unique_owner[0] 
          print("\n\nHorizontal Winning condition met, User: {0} Won! Row: {1} \n\n".format(winner_id, i))
          return winner_id     

        # Checking for Vertical Wins
        vertical_moves = Move.query(Move.game_id == game_id, Move.y == i) 
        vertical_moves = [h.user_id for h in vertical_moves]  

        unique_owner = list( set(vertical_moves) )                

        if None not in unique_owner and len(unique_owner) == 1:
          winner_id = unique_owner[0] 
          print("\n\n Vertical Winning condition met, User: {0} Won!, Column: {1} \n\n".format(winner_id, i))
          return winner_id            

      # Checking Cross Wins
      diagonal_moves = []
      for i in range(0,3):
        m = Move.query(Move.x == i, Move.y == i).fetch()[0]

      unique_owner = list(set(diagonal_moves))

      if None not in unique_owner and len(unique_owner) == 1:
        winner_id = unique_owner[0] 
        print("\n\n Diagonal Winning condition met, User: {0} Won!, Column: {1} \n\n".format(winner_id, i))
        return winner_id   

      # Checking Cross Wins

      diagonal_moves = []
      for i in range(0,3):
        m = Move.query(Move.x == i, Move.y == 2-i).fetch()[0]
        diagonal_moves.append(m.user_id)
        diagonal_moves.append(m.user_id)       

      unique_owner = list(set(diagonal_moves))

      if None not in unique_owner and len(unique_owner) == 1:
        winner_id = unique_owner[0] 
        print("\n\n Diagonal Winning condition met, User: {0} Won!, Column: {1} \n\n".format(winner_id, i))
        return winner_id  

      print("\n\n No winning conditions met \n\n")
      return False                


    @staticmethod
    def _get_players_in_game(game_id):

      moves = Move.query(Move.game_id == game_id).fetch()

      if len(moves) == 0:
        return StringMessage(message = "Invalid move parameters. no game found" )


      print("Getting players in game...")
      user_ids = []

      for move in moves:
        user_id = move.user_id
        # print("checking for ID: {0}".format( user_id) )

        if user_id not in user_ids and user_id != None:
          # print("ID: {0} was inserted".format( user_id) )
          user_ids.append(user_id)

      print(user_ids)
      if len(user_ids) == 2:
        player1 = user_ids[0]
        player2 = user_ids[1]
      elif len(user_ids) == 1:
        player1 = user_ids[0]
        player2 = None 
      else:
        player1 = None
        player2 = None                 
        
      print(player2, player1) 
      return [player1, player2]     







    # @endpoints.method(request_message=USER_REQUEST,
    #                   response_message=StringMessage,
    #                   path='user',
    #                   name='create_user',
    #                   http_method='POST')
    # def create_user(self, request):
    #     """Create a User. Requires a unique username"""
    #     if User.query(User.name == request.user_name).get():
    #         raise endpoints.ConflictException(
    #                 'A User with that name already exists!')
    #     user = User(name=request.user_name, email=request.email)
    #     user.put()
    #     return StringMessage(message='User {} created!'.format(
    #             request.user_name))

    # @endpoints.method(request_message=NEW_GAME_REQUEST,
    #                   response_message=GameForm,
    #                   path='game',
    #                   name='new_game',
    #                   http_method='POST')
    # def new_game(self, request):
    #     """Creates new game"""
    #     user = User.query(User.name == request.user_name).get()
    #     if not user:
    #         raise endpoints.NotFoundException(
    #                 'A User with that name does not exist!')
    #     try:
    #         game = Game.new_game(user.key, request.min,
    #                              request.max, request.attempts)
    #     except ValueError:
    #         raise endpoints.BadRequestException('Maximum must be greater '
    #                                             'than minimum!')

    #     # Use a task queue to update the average attempts remaining.
    #     # This operation is not needed to complete the creation of a new game
    #     # so it is performed out of sequence.
    #     taskqueue.add(url='/tasks/cache_average_attempts')
    #     return game.to_form('Good luck playing Guess a Number!')

    # @endpoints.method(request_message=GET_GAME_REQUEST,
    #                   response_message=GameForm,
    #                   path='game/{urlsafe_game_key}',
    #                   name='get_game',
    #                   http_method='GET')
    # def get_game(self, request):
    #     """Return the current game state."""
    #     game = get_by_urlsafe(request.urlsafe_game_key, Game)
    #     if game:
    #         return game.to_form('Time to make a move!')
    #     else:
    #         raise endpoints.NotFoundException('Game not found!')

    # # @endpoints.method(request_message=MAKE_MOVE_REQUEST,
    # #                   response_message=GameForm,
    # #                   path='game/{urlsafe_game_key}',
    # #                   name='make_move',
    # #                   http_method='PUT')
    # # def make_move(self, request):
    # #     """Makes a move. Returns a game state with message"""
    # #     game = get_by_urlsafe(request.urlsafe_game_key, Game)
    # #     if game.game_over:
    # #         return game.to_form('Game already over!')

    # #     game.attempts_remaining -= 1
    # #     if request.guess == game.target:
    # #         game.end_game(True)
    # #         return game.to_form('You win!')

    # #     if request.guess < game.target:
    # #         msg = 'Too low!'
    # #     else:
    # #         msg = 'Too high!'

    # #     if game.attempts_remaining < 1:
    # #         game.end_game(False)
    # #         return game.to_form(msg + ' Game over!')
    # #     else:
    # #         game.put()
    # #         return game.to_form(msg)

    # @endpoints.method(response_message=ScoreForms,
    #                   path='scores',
    #                   name='get_scores',
    #                   http_method='GET')
    # def get_scores(self, request):
    #     """Return all scores"""
    #     return ScoreForms(items=[score.to_form() for score in Score.query()])

    # @endpoints.method(request_message=USER_REQUEST,
    #                   response_message=ScoreForms,
    #                   path='scores/user/{user_name}',
    #                   name='get_user_scores',
    #                   http_method='GET')
    # def get_user_scores(self, request):
    #     """Returns all of an individual User's scores"""
    #     user = User.query(User.name == request.user_name).get()
    #     if not user:
    #         raise endpoints.NotFoundException(
    #                 'A User with that name does not exist!')
    #     scores = Score.query(Score.user == user.key)
    #     return ScoreForms(items=[score.to_form() for score in scores])

    # @endpoints.method(response_message=StringMessage,
    #                   path='games/average_attempts',
    #                   name='get_average_attempts_remaining',
    #                   http_method='GET')
    # def get_average_attempts(self, request):
    #     """Get the cached average moves remaining"""
    #     return StringMessage(message=memcache.get(MEMCACHE_MOVES_REMAINING) or '')

    @staticmethod
    def _cache_average_attempts():
        """Populates memcache with the average moves remaining of Games"""
        games = Game.query(Game.game_over == False).fetch()
        if games:
            count = len(games)
            total_attempts_remaining = sum([game.attempts_remaining
                                        for game in games])
            average = float(total_attempts_remaining)/count
            memcache.set(MEMCACHE_MOVES_REMAINING,
                         'The average moves remaining is {:.2f}'.format(average))


api = endpoints.api_server([GuessANumberApi])
