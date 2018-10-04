from PythonClientAPI.game.PointUtils import *
from PythonClientAPI.game.Entities import FriendlyUnit, EnemyUnit, Tile
from PythonClientAPI.game.Enums import Team
from PythonClientAPI.game.World import World
from PythonClientAPI.game.TileUtils import TileUtils

'''
establish a corner and defend it
'''

class PlayerAI:

    def __init__(self):
        ''' Initialize! '''
        self.turn_count = 0             # game turn count
        self.target = None              # target to send unit to! (a tile)
        self.outbound = True            # is the unit leaving, or returning?
        self.safehouse = None
        self.mode = 'SETUP'
        # SETUP [setup small square]
        # PATROL
        # OVERRIDE
        self.base_corners = [] # establish 6x6 corner
        self.curr_corner_goal = 0
        self.setup_turn_limit = 30          # don't try to set up past this turn
        self.patrol_position = (14, 14)     # default/placeholder value
        self.player = 1 # default
        # values used to determine how valuable a potential patrol path is
        self.neutral_value = 1
        self.enemy_value = 2
        self.enemy_body_value = 10

        self.unacceptable_path_value = 10   # if a calculated path_value is less than this value, expand the patrol
        self.territory_streak = 0           # how many territory tiles in a row unit has traversed. the higher it is,
                                            # the more unacceptable_path_value is lowered during calculations
        self.patrol_updated = False         # Flag needed to update unit's movement if the patrol point was changed while
                                            # unit was travelling to the old patrol point


        #self.bravery = 4



    def do_move(self, world, friendly_unit, enemy_units):
        '''
        This method is called every turn by the game engine.
        Make sure you call friendly_unit.move(target) somewhere here!

        Below, you'll find a very rudimentary strategy to get you started.
        Feel free to use, or delete any part of the provided code - Good luck!

        :param world: world object (more information on the documentation)
            - world: contains information about the game map.
            - world.path: contains various pathfinding helper methods.
            - world.util: contains various tile-finding helper methods.
            - world.fill: contains various flood-filling helper methods.

        :param friendly_unit: FriendlyUnit object
        :param enemy_units: list of EnemyUnit objects
        '''

        # increment turn count
        self.turn_count += 1

        # positions for the initial box
        if self.turn_count == 1:
            if friendly_unit.position == (3, 3):
                self.player = 1
                self.base_corners = [(1, 1), (1, 7), (7, 7), (7, 1), (4, 1), (4, 2)]
            elif friendly_unit.position == (26, 3):
                self.player = 2
                self.base_corners = [(28, 1), (28, 7), (22, 7), (22, 1), (25, 1), (25, 2)]
            elif friendly_unit.position == (26, 26):
                self.player = 3
                self.base_corners = [(26, 28), (28, 28), (28, 22), (22, 22), (22, 28), (25, 28), (25, 27)]
            else:
                self.player = 4
                self.base_corners = [(3, 28), (1, 28), (1, 22), (7, 22), (7, 28), (4, 28), (4, 27)]
            self.patrol_position = friendly_unit.position
            self.expand_patrol(6)

        # if unit is dead, stop making moves.
        if friendly_unit.status == 'DISABLED':
            print("Turn {0}: Disabled - skipping move.".format(str(self.turn_count)))
            self.target = None
            return

        if world.position_to_tile_map[friendly_unit.position].is_friendly:
            self.territory_streak += 1
        else:
            self.territory_streak = 0

        # score easy kills around the head -- move into bodies and heads
        neighbours = world.get_neighbours(friendly_unit.position)
        for neighbour in neighbours:
            neighbour_tile = world.position_to_tile_map[neighbours[neighbour]]
            body_in_range = neighbour_tile.body
            if body_in_range is not None and body_in_range != friendly_unit.team:
                self.target = neighbour_tile
                self.mode=='OVERRIDE'
                # break because can only make 1 move
                break
            head_in_range = neighbour_tile.head
            if head_in_range is not None and head_in_range != friendly_unit.team:
                self.target =  neighbour_tile
                self.mode=='OVERRIDE'
                # break because can only make 1 move
                break

        # if unit reaches the target point, set destination to false and set target back to None and decide the next mode/course of action
        if self.target is not None and friendly_unit.position == self.target.position:
            # self.destination = False
            self.target = None
            self.curr_corner_goal += 1
            # end the setup if it's done
            if self.mode=='SETUP' and self.curr_corner_goal >= len(self.base_corners):
                print("> setup done, begin patrol")
                self.mode = 'PATROL'
            if self.mode == 'PATROL':
                # if unit is on patrol point
                if friendly_unit.position == self.patrol_position:
                    # pick one of the two edges of your territory to patrol
                    self.target = self.pick_patrol_path(world, friendly_unit)
                # if in territory, set target to the patrol point
                elif world.position_to_tile_map[friendly_unit.position].is_friendly:
                    self.target = world.position_to_tile_map[self.patrol_position]
                # otherwise, return to territory first to finish capturing territory
                else:
                    self.target = world.util.get_closest_friendly_territory_from(friendly_unit.position, friendly_unit.snake)

        # update target if the patrol has changed
        if self.mode == 'PATROL' and self.patrol_updated:
            self.target = world.position_to_tile_map[self.patrol_position]
            self.patrol_updated = False

        # if no target is set, choose a new one
        if self.target is None:
            if self.mode=='SETUP':
                if self.turn_count > self.setup_turn_limit:
                    self.mode = 'PATROL'
                # go to next corner goal based on progress
                elif self.curr_corner_goal < len(self.base_corners):
                    self.target = world.position_to_tile_map[self.base_corners[self.curr_corner_goal]]
            if self.mode=='PATROL':
                # pullback a bit and start patrolling again
                self.pullback_patrol(1)
                self.target = world.position_to_tile_map[self.patrol_position]

        # return to normal operations
        if self.mode=='OVERRIDE':
            self.mode == 'PATROL'

        #TODO: handle nonetype/no move?
        # set next move as the next point in the path to target
        next_move = world.path.get_shortest_path(friendly_unit.position, self.target.position, friendly_unit.snake)[0]

        # move!
        friendly_unit.move(next_move)
        print("Turn {0}: currently at {1}, moving to {2} as dictated by mode {3}.".format(
            str(self.turn_count),
            str(friendly_unit.position),
            str(self.target.position),
            self.mode
        ))

    def expand_patrol(self, intensity):
        print("> patrol expanded")
        self.patrol_updated = True
        if self.player == 1:
            self.patrol_position = self.patrol_position[0] + intensity, self.patrol_position[1] + intensity
        elif self.player == 2:
            self.patrol_position = self.patrol_position[0] - intensity, self.patrol_position[1] + intensity
        elif self.player == 3:
            self.patrol_position = self.patrol_position[0] - intensity, self.patrol_position[1] - intensity
        else:
            self.patrol_position = self.patrol_position[0] + intensity, self.patrol_position[1] - intensity

    def pullback_patrol(self, intensity):
        self.patrol_updated = True
        if self.player == 1:
            self.patrol_position = self.patrol_position[0] - intensity, self.patrol_position[1] - intensity
        elif self.player == 2:
            self.patrol_position = self.patrol_position[0] + intensity, self.patrol_position[1] - intensity
        elif self.player == 3:
            self.patrol_position = self.patrol_position[0] + intensity, self.patrol_position[1] + intensity
        else:
            self.patrol_position = self.patrol_position[0] - intensity, self.patrol_position[1] + intensity

    # return the final tile of the path that is more valuable to traverse
    def pick_patrol_path(self, world, friendly_unit):
        if self.player == 1:
            # the y of the end of the vertical patrol path
            vert_end = 1
            # the x of the end of the vertical patrol path
            horz_end = 1
        elif self.player == 2:
            vert_end = 1
            horz_end = 28
        elif self.player == 3:
            vert_end = 28
            horz_end = 28
        else:
            vert_end = 28
            horz_end = 1
        # final point of the last tile on this path
        vertical_path_end_position = friendly_unit.position[0], vert_end
        # path from unit to the end of this path
        vertical_path = world.path.get_shortest_path(friendly_unit.position, vertical_path_end_position, friendly_unit.snake)
        # path from end of this path the closest territory
        home_point = world.util.get_closest_friendly_territory_from(vertical_path_end_position, friendly_unit.snake).position
        return_path = world.path.get_shortest_path(vertical_path_end_position, home_point, friendly_unit.snake)
        # entire path from unit to territory
        full_vertical_path = vertical_path + return_path
        # evaluate how valuable taking this path may be
        vert_value = self.determine_path_value(world, friendly_unit, full_vertical_path)

        horizonal_path_end_position = horz_end, friendly_unit.position[1]
        horizonal_path = world.path.get_shortest_path(friendly_unit.position, horizonal_path_end_position, friendly_unit.snake)
        home_point = world.util.get_closest_friendly_territory_from(horizonal_path_end_position, friendly_unit.snake).position
        return_path = world.path.get_shortest_path(horizonal_path_end_position, home_point, friendly_unit.snake)
        full_horizontal_path = horizonal_path + return_path
        horz_value = self.determine_path_value(world, friendly_unit, full_horizontal_path)

        # inch out patrol point if the values for these paths are low
        if max(vert_value, horz_value) < self.unacceptable_path_value + self.territory_streak:
            self.expand_patrol(1)

        if vert_value > horz_value:
            return world.position_to_tile_map[vertical_path_end_position]
        else:
            return world.position_to_tile_map[horizonal_path_end_position]

    def determine_path_value(self, world, friendly_unit, path):
        path_value = 0
        # joins the list of hypothetical body points to the set of current body points
        body = friendly_unit.body | set(path)
        territory = friendly_unit.territory
        unit = path[-2]
        next_move = path[-1]
        fill_set = world.fill.flood_fill(body, territory, unit, next_move)
        for point in fill_set:
            tile = world.position_to_tile_map[point]
            if tile.body is not None and tile.body != friendly_unit.team:
                path_value += self.enemy_body_value
            elif tile.is_neutral:
                path_value += self.neutral_value
            elif tile.is_enemy:
                path_value += self.enemy_value
        return path_value




