# algoTrading
## Running daytrading strategies
### *** IMPORTANT WARNING ***
This repo is for building, testing and running trading strategies through Interactive Brokers. It is an algorithmic extension of the ib-insync package. It will only work with a working TWS or IB Gateway connection.
***   ***END WARNING*** ***
### 1. Make your Algos
The first step is to make an **Algo** which is simply a class of trading strategy paired with the parameters needed to run it. The Algo is made with a config (*.ini) file and looks like this: 
~~~ ini
[Parameters]
strategy = Trending
contract = ES
tickperbar = 250
window = 14
quantity = 20000
# ect...
~~~
It'll need a name like 'bob.ini' and must live in the *algos* folder. 
You'll obviously need to know your strategy class and all the parameters to make an Algo but once you do you can create, store and delete as many as you want and we can choose what is and is not added to git. 
Examples of config files with the full parameters needed to run each strategy class can be found in algos/examples. 
A full algo config is output after each run along with the rest of the run data.
### 2. Setup main.ini
To determine which algos are run and how at run time, we must set up the main config (**main.ini**). Remember our Algo 'bob.ini' from ealier? Well this is where we put get to put him and his algo friends to the test. The main.ini lives in the main folder and looks like this:
~~~ ini
framework = concurrent
# way in which to run the algos
algos = bob,algo2,algo3 #ect.
# algos to run
runtime = 40
# how long to run the algos (default: seconds)
revtime = 30
# how long to track data before running algos (default: seconds)
time_mult = 60
# time multiplier to apply to the times above. ex. time_mult = 60 -> minutes
gateway = False
# True if using IBGateway, False if TWS
ibc = False
# True if using IBC, False if not
# Setting gateway to False will force ibc to be False since IBC is Gateway only
save_data = True
# Whether or not to save the run data
file_exts = csv,xlsx
# The file types for the saved data if save_data is True
# csv and xlsx are the only options to choose from at the moment
~~~
You probably won't need to change your main.ini very often and it shoudn't ever really need to be managed with git unless changes to the fields in the main.ini occur (which is very possible).
### 3. Setup IB
This step is easy, it's just starting up TWS/IBGateway or doing nothing if ibc is 'True' in the main.ini (and ibc is working obviously).
### 4. Run 'python trade.py' from the main folder
After the run, results can be found in the data folder where the most recent run corresponds to the most recent date.
### 5. Profit
