import pyqtgraph as pg
# from IPython import embed


class PyqtgraphSettings:
    # Global pyqtgraph settings
    pg.setConfigOption('background', pg.mkColor('w'))
    pg.setConfigOption('foreground', pg.mkColor('k'))
    pg.setConfigOption('useOpenGL', False)
    pg.setConfigOption('antialias', False)
    pg.setConfigOption('useNumba', False)
    pg.setConfigOption('enableExperimental', False)
    pg.setConfigOption('leftButtonPan', True)
    pg.setConfigOption('imageAxisOrder', 'row-major')


class DataPlotter:
    def __init__(self, master_plot):
        self.master_plot = master_plot

    def clear_plot_data(self, name):
        # check if there is already roi data plotted and remove it
        item_list = self.master_plot.items.copy()
        for item in item_list:
            if item.name() is not None:
                if item.name().startswith(name):
                    self.master_plot.removeItem(item)

    def update_video_plot(self, time_point, y_range):
        self.clear_plot_data(name='video')
        plot_data_item = pg.PlotDataItem(
            [time_point, time_point], [y_range[0], y_range[1]],
            pen=pg.mkPen(color=(255, 0, 255)),
            name=f'video_time',
            skipFiniteCheck=True,
            tip=None,
        )
        # Add plot item to the plot widget
        self.master_plot.addItem(plot_data_item)

    def update(self, time_axis, data, meta_data=None):
        # check if there is already roi data plotted and remove
        self.clear_plot_data(name='data')

        cc = 0
        for t, y in zip(time_axis, data):
            # get meta data
            if meta_data is not None:
                color = meta_data[cc]['color']
                lw = meta_data[cc]['lw']
                plot_name = f'data_{meta_data[cc]["name"]}'
            else:
                color = '#000000'  # black
                lw = 1
                plot_name = f'data_{cc}'
            # Create new  plot item
            plot_data_item = pg.PlotDataItem(
                t, y,
                pen=pg.mkPen(color=color, width=lw),
                # name=f'data_{cc}',
                name=plot_name,
                skipFiniteCheck=True,
                tip=None,
            )
            # plot_data_item.setDownsampling(auto=True, method='peak')
            # Add plot item to the plot widget
            self.master_plot.addItem(plot_data_item)
            cc += 1

    def update_global(self, time_axis, data, meta_data=None):
        # self.clear_global_data()
        self.clear_plot_data(name='global')
        cc = 0  # index of data set (0 = the first global data set, and so on)
        for t, y_data in zip(time_axis, data):
            # Each column in global data set can be a trace
            for y in y_data.T:
                # get meta data
                if meta_data is not None:
                    color = meta_data[cc]['color']
                    lw = meta_data[cc]['lw']
                    plot_name = f'global_{meta_data[cc]["name"]}'
                else:
                    color = '#000000'  # black
                    lw = 1
                    plot_name = f'global_{cc}'

                # Create new  plot item
                plot_data_item = pg.PlotDataItem(
                    t, y,
                    pen=pg.mkPen(color=color, width=lw),
                    # name=f'global_{cc}',
                    name=plot_name,
                    skipFiniteCheck=True,
                    tip=None,
                    # autoDownsample=True,
                    # clipToView=True
                )
                # plot_data_item.setClipToView(True)
                # plot_data_item.setDownsampling(auto=True)
                # Add plot item to the plot widget
                self.master_plot.addItem(plot_data_item)
            cc += 1
