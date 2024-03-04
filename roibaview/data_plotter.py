import pyqtgraph as pg
from IPython import embed


class PyqtgraphSettings:
    # Global pyqtgraph settings
    pg.setConfigOption('background', pg.mkColor('w'))
    pg.setConfigOption('foreground', pg.mkColor('k'))
    # pg.setConfigOption('useOpenGL', True)
    pg.setConfigOption('antialias', False)
    pg.setConfigOption('imageAxisOrder', 'row-major')


class DataPlotter:
    def __init__(self, master_plot):
        self.master_plot = master_plot

    def clear_roi_data(self):
        # check if there is already roi data plotted and remove it
        item_list = self.master_plot.items.copy()
        for item in item_list:
            if item.name() is not None:
                if item.name().startswith('data'):
                    self.master_plot.removeItem(item)

    def clear_global_data(self):
        # check if there is already global data plotted and remove it
        item_list = self.master_plot.items.copy()
        for item in item_list:
            if item.name() is not None:
                if item.name().startswith('global'):
                    self.master_plot.removeItem(item)

    def update(self, time_axis, data):
        # check if there is already roi data plotted and remove it
        self.clear_roi_data()

        cc = 0
        for t, y in zip(time_axis, data):
            # Create new  plot item
            plot_data_item = pg.PlotDataItem(
                t, y,
                pen=pg.mkPen(color=(0, 0, 0)),
                # name=f'{self.data_handler.data_name}_ROI{self.data_handler.roi_id}',
                name=f'data_{cc}',
                skipFiniteCheck=True,
                tip=None,
            )

            # Add plot item to the plot widget
            self.master_plot.addItem(plot_data_item)
            cc += 1

    def update_global(self, time_axis, data):
        self.clear_global_data()
        cc = 0
        for t, y_data in zip(time_axis, data):
            # Each column in global data set can be a trace
            for y in y_data.T:
                # Create new  plot item
                plot_data_item = pg.PlotDataItem(
                    t, y,
                    pen=pg.mkPen(color=(255, 0, 0)),
                    # name=f'{self.data_handler.data_name}_ROI{self.data_handler.roi_id}',
                    name=f'global_{cc}',
                    skipFiniteCheck=True,
                    tip=None,
                )

                # Add plot item to the plot widget
                self.master_plot.addItem(plot_data_item)
                cc += 1
