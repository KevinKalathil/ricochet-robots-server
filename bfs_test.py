from typing import List, Tuple, Optional, Dict
from collections import deque

# Directions (dx, dy) and name
DIRECTIONS = {
    "Right": (1, 0),
    "Left": (-1, 0),
    "Up": (0, -1),
    "Down": (0, 1),
}

def is_blocked_by_wall(grid: List[List[int]], x: int, y: int, dx: int, dy: int) -> bool:
    """
    Return True if movement from (x,y) to (x+dx, y+dy) is blocked by a wall (either current cell or target cell).
    grid[y][x] uses bitmask: 1=N, 2=E, 4=S, 8=W
    """
    rows = len(grid)
    cols = len(grid[0])
    nx, ny = x + dx, y + dy
    # out of bounds treated as blocked
    if not (0 <= nx < cols and 0 <= ny < rows):
        return True

    # moving Up (dy == -1): blocked if current has North or target has South
    if dx == 0 and dy == -1:
        return (grid[y][x] & 1) != 0 or (grid[ny][nx] & 4) != 0
    # moving Down (dy == 1): blocked if current has South or target has North
    if dx == 0 and dy == 1:
        return (grid[y][x] & 4) != 0 or (grid[ny][nx] & 1) != 0
    # moving Right (dx == 1): blocked if current has East or target has West
    if dx == 1 and dy == 0:
        return (grid[y][x] & 2) != 0 or (grid[ny][nx] & 8) != 0
    # moving Left (dx == -1): blocked if current has West or target has East
    if dx == -1 and dy == 0:
        return (grid[y][x] & 8) != 0 or (grid[ny][nx] & 2) != 0

    return True  # fallback: block

def slide_until_block(grid: List[List[int]], start: Tuple[int,int],
                     dx: int, dy: int, occupied: set) -> Tuple[int,int]:
    """
    Slide from start (x,y) along (dx,dy) until the next cell would be blocked by wall or occupied.
    Return final (x,y).
    """
    x, y = start
    rows = len(grid)
    cols = len(grid[0])

    while True:
        nx, ny = x + dx, y + dy
        # stop if out of bounds or wall between current and next
        if not (0 <= nx < cols and 0 <= ny < rows):
            break
        if is_blocked_by_wall(grid, x, y, dx, dy):
            break
        # stop if occupied (there is a robot at next cell)
        if (nx, ny) in occupied:
            break
        # otherwise move to nx,ny and continue
        x, y = nx, ny

    return (x, y)

def encode_positions(positions: List[Tuple[int,int]]) -> Tuple[Tuple[int,int], ...]:
    """Canonical encoding for visited set"""
    return tuple(positions)

def solve_board(board: Dict, rows = 10, cols = 10) -> Optional[List[Dict]]:
    """
    BFS solver.
    board: dict with keys: 'rows','cols','grid' (2D int list), 'robots' (list of [x,y]),
           'target' (x,y)
    Returns list of moves: [{ 'robot': i, 'dir': 'Right', 'to': [x,y] }, ...] or None.
    """
    grid = board["grid"]
    print("Grid:", grid)
    robots = [tuple(r) for r in board["robots"]]  # list of (x,y)
    target = tuple(board["target"])               # (x,y)
    num_robots = len(robots)

    # BFS queue: each node = (positions_list, moves_list)
    start_positions = robots
    print("Start positions:", start_positions)
    start_key = encode_positions(start_positions)
    print("Start key:", start_key)

    q = deque()
    q.append((start_positions, []))
    visited = {start_key}

    while q:
        positions, moves = q.popleft()

        # check if any robot at target
        if any(pos == target for pos in positions):
            # return moves as sequence of dicts
            return moves

        # for each robot, try sliding in each direction
        for ridx in range(num_robots):
            for dname, (dx, dy) in DIRECTIONS.items():
                occupied = set(positions)  # set of occupied cells
                start = positions[ridx]
                new_pos = slide_until_block(grid, start, dx, dy, occupied)

                # if no movement, skip
                if new_pos == start:
                    continue

                # build new positions list
                new_positions = list(positions)
                new_positions[ridx] = new_pos
                key = encode_positions(new_positions)
                if key in visited:
                    continue
                visited.add(key)

                # append move record
                move_record = {
                    "robot": ridx,
                    "dir": dname,
                    "to": [new_pos[0], new_pos[1]]
                }
                q.append((new_positions, moves + [move_record]))

    # no solution
    return None



solution = solve_board({"rows":10,"cols":10,"grid":[[9,1,1,1,1,1,1,1,1,3],[8,0,0,8,1,8,0,8,0,2],[8,0,0,0,8,0,0,0,8,10],[8,0,0,0,0,1,0,8,0,2],[8,0,0,0,0,0,0,0,1,10],[8,0,0,8,0,0,0,9,8,2],[8,0,0,0,0,1,0,0,0,2],[8,0,0,1,0,0,0,0,0,2],[8,0,0,1,8,8,0,0,0,2],[12,4,12,4,4,5,5,4,4,6]],"robots":[[7,4],[0,1],[4,0]],"target":[5,7]})
print("Solution:", solution)