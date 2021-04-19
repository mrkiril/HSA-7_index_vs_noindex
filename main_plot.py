from utils import FileReader

if __name__ == '__main__':
    import matplotlib.pyplot as plt
    # line 1 points
    DATA_FOR_MATPLOTLIB = FileReader.read_data(fie_name='app/avr_time_80.csv')
    # line 1 points
    x1 = [int(data["count"]) for data in DATA_FOR_MATPLOTLIB]
    y1 = [float(data["index"]) for data in DATA_FOR_MATPLOTLIB]

    # line 2 points
    x2 = [int(data["count"]) for data in DATA_FOR_MATPLOTLIB]
    y2 = [float(data["noindex"]) for data in DATA_FOR_MATPLOTLIB]

    # plotting the line 1 - 2 points
    fig, (ax1, ax2) = plt.subplots(2)
    fig.suptitle('Index vs NoIndex')
    ax1.set_title('Index plot')
    ax1.plot(x1, y1)
    ax2.set_title('NoIndex plot')
    ax2.plot(x2, y2)

    ax1.set(xlabel='Count of rows (M)', ylabel='time, ms')
    ax2.set(xlabel='Count of rows (M)', ylabel='time, ms')
    # # Set a title of the current axes.
    plt.legend()
    # Display a figure.
    plt.show()
