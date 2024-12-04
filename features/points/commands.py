# features/points/commands.py\
import logging
from twitchio.ext import commands
from utils.decorators import rate_limited
from datetime import datetime, timezone
from sqlalchemy import text

logger = logging.getLogger(__name__)

class PointsCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.points_name = "points"  # You can customize this name

    @commands.command(name='points')
    @rate_limited(cooldown=10)
    async def check_points(self, ctx):
        """Check your current points balance"""
        user_id = str(ctx.author.id)

        try:
            async with self.bot.db.session_scope() as session:
                # Attempt to retrieve the user's points
                result = await session.execute(
                    text('SELECT points FROM user_points WHERE user_id = :user_id'),
                    {'user_id': user_id}
                )
                row = result.first()

                # Insert new user if they do not exist in the table
                if row is None:
                    points = 0
                    await session.execute(
                        text('''
                            INSERT INTO user_points (user_id, points, total_earned, last_updated)
                            VALUES (:user_id, :points, :total_earned, :last_updated)
                        '''),
                        {
                            'user_id': user_id,
                            'points': points,
                            'total_earned': points,
                            'last_updated': datetime.now(timezone.utc)
                        }
                    )
                    await session.commit()
                    logger.info(f"New user {ctx.author.name} ({user_id}) added with {points} points.")
                else:
                    points = row[0]
                    logger.info(f"User {ctx.author.name} ({user_id}) has {points} points.")

                # Send the user's points balance
                await ctx.send(f"@{ctx.author.name} You have {points} {self.points_name}!")

        except Exception as e:
            logger.error(f"Error checking points for user {user_id} ({ctx.author.name}): {e}")
            await ctx.send(f"@{ctx.author.name} Error checking points!")



    @commands.command(name='top')
    @rate_limited(cooldown=30)
    async def show_leaderboard(self, ctx):
        """Show points leaderboard"""
        try:
            async with self.bot.db.session_scope() as session:
                result = await session.execute(text('''
                    SELECT up.points, u.username 
                    FROM user_points up
                    JOIN users u ON up.user_id = u.twitch_id
                    ORDER BY up.points DESC LIMIT 5
                '''))
                rows = result.all()
                
                if rows:
                    leaders = [f"#{i+1} {username}: {points}" for i, (points, username) in enumerate(rows)]
                    await ctx.send(f"Top {self.points_name}: {' | '.join(leaders)}")
                else:
                    await ctx.send("No point earners yet!")
        except Exception as e:
            logger.error(f"Error showing leaderboard: {e}")
            await ctx.send("Error fetching leaderboard!")

    @commands.command(name='give')
    @rate_limited(cooldown=10)
    async def give_points(self, ctx, target: str = None, amount: str = None):
        """Give points to another user"""
        if not target or not amount:
            await ctx.send(f"Usage: !give <username> <amount>")
            return
            
        try:
            amount = int(amount)
            if amount <= 0:
                await ctx.send(f"@{ctx.author.name} Amount must be positive!")
                return
                
            # Get target user
            async with self.bot.db.session_scope() as session:
                query = text('SELECT twitch_id FROM users WHERE LOWER(username) = :name')
                result = await session.execute(query, {'name': target.lower()})
                target_id = result.scalar()
                
                if not target_id:
                    await ctx.send(f"@{ctx.author.name} User not found!")
                    return
                
                # Try transferring points
                sender_points = await self.bot.points_manager.get_points(str(ctx.author.id))
                if sender_points >= amount:
                    now = datetime.now(timezone.utc)
                    update_query = text('''
                        UPDATE user_points 
                        SET points = CASE
                            WHEN user_id = :sender_id THEN points - :amount
                            WHEN user_id = :target_id THEN points + :amount
                        END,
                        last_updated = :now
                        WHERE user_id IN (:sender_id, :target_id)
                    ''')
                    await session.execute(update_query, {
                        'sender_id': str(ctx.author.id),
                        'target_id': target_id,
                        'amount': amount,
                        'now': now
                    })
                    await ctx.send(f"@{ctx.author.name} gave {amount} {self.points_name} to @{target}!")
                else:
                    await ctx.send(f"@{ctx.author.name} You don't have enough {self.points_name}!")
                    
        except ValueError:
            await ctx.send(f"@{ctx.author.name} Invalid amount!")
        except Exception as e:
            logger.error(f"Error giving points: {e}")
            await ctx.send(f"@{ctx.author.name} Error giving points!")

    @commands.command(name='setpoints')
    async def set_points(self, ctx, target: str = None, amount: str = None):
        """Set a user's points (mod only)"""
        if not ctx.author.is_mod:
            return
            
        if not target or not amount:
            await ctx.send("Usage: !setpoints <username> <amount>")
            return
            
        try:
            amount = int(amount)
            if amount < 0:
                await ctx.send("Amount cannot be negative!")
                return
                
            async with self.bot.db.session_scope() as session:
                now = datetime.now(timezone.utc)
                query = text('''
                    UPDATE user_points 
                    SET points = :amount,
                        last_updated = :now
                    WHERE user_id = (
                        SELECT twitch_id 
                        FROM users 
                        WHERE LOWER(username) = :username
                    )
                ''')
                await session.execute(query, {
                    'amount': amount,
                    'now': now,
                    'username': target.lower()
                })
                await ctx.send(f"Set @{target}'s {self.points_name} to {amount}!")
                
        except ValueError:
            await ctx.send("Invalid amount!")
        except Exception as e:
            logger.error(f"Error setting points: {e}")
            await ctx.send("Error setting points!")