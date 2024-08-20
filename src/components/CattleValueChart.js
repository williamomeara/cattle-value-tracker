import React from 'react';
import { Line } from 'react-chartjs-2';
import { Chart as ChartJS, CategoryScale, LinearScale, LineElement, PointElement, Title, Tooltip, Legend, TimeScale } from 'chart.js';
import 'chartjs-adapter-date-fns'; // Import date-fns for date handling
import PropTypes from 'prop-types';


// Register the necessary components for Chart.js
ChartJS.register(
  CategoryScale,
  LinearScale,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend,
  TimeScale // Register the TimeScale component
);

// Individual Cattle Value Chart
const IndividualCattleValueChart = ({ cattleList }) => {
  const individualData = {
    labels: [], // Empty because time data will be dynamic
    datasets: cattleList.map((cattle, index) => ({
      label: `${cattle.type.replace('_', ' ').toUpperCase()} - Weight: ${cattle.weight} kg`,
      data: cattle.values.map(v => ({ x: v.date, y: v.value * cattle.weight / 100 })), // Convert cents to dollars
      borderColor: `rgba(${index * 50 % 255}, ${index * 100 % 255}, ${index * 150 % 255}, 1)`,
      backgroundColor: `rgba(${index * 50 % 255}, ${index * 100 % 255}, ${index * 150 % 255}, 0.5)`,
      fill: false,
      pointStyle: 'circle',
    })),
  };

  const options = {
    responsive: true,
    plugins: {
      legend: {
        position: 'top',
        onClick: (e, legendItem, legend) => {
          const index = legendItem.datasetIndex;
          const meta = legend.chart.getDatasetMeta(index);

          meta.hidden = meta.hidden === null ? !legend.chart.data.datasets[index].hidden : null;

          legend.chart.update();
        },
      },
      tooltip: {
        mode: 'index',
        intersect: false,
        callbacks: {
          label: function(context) {
            const value = context.raw.y.toFixed(2); // Format value to 2 decimal places
            return `$${value}`; // Show value in dollars
          }
        }
      },
    },
    scales: {
      x: {
        type: 'time',
        time: {
          unit: 'month',
        },
        title: {
          display: true,
          text: 'Date',
        },
      },
      y: {
        title: {
          display: true,
          text: 'Value (USD)',
        },
        ticks: {
          callback: (value) => `$${value.toFixed(2)}`, // Format y-axis labels
        },
      },
    },
  };

  return (
    <div>
      <h2>Cattle Value Over Time</h2>
      <Line data={individualData} options={options} />
    </div>
  );
};

// Total Herd Value Chart
const TotalHerdValueChart = ({ cattleList }) => {
  const aggregateHerdValues = (cattleList) => {
    const valueMap = {};

    cattleList.forEach(cattle => {
      cattle.values.forEach(v => {
        if (!valueMap[v.date]) {
          valueMap[v.date] = 0;
        }
        valueMap[v.date] += v.value * cattle.weight / 100; // Convert cents to dollars
      });
    });

    return Object.keys(valueMap).map(date => ({
      x: date,
      y: valueMap[date],
    }));
  };

  const herdData = {
    labels: [], // Empty because time data will be dynamic
    datasets: [{
      label: 'Total Herd Value',
      data: aggregateHerdValues(cattleList),
      borderColor: 'rgba(75, 192, 192, 1)',
      backgroundColor: 'rgba(75, 192, 192, 0.5)',
      fill: false,
    }],
  };

  const options = {
    responsive: true,
    plugins: {
      legend: {
        position: 'top',
        display: false, // Hide legend in the herd data chart
      },
      tooltip: {
        mode: 'index',
        intersect: false,
        callbacks: {
          label: function(context) {
            const value = context.raw.y.toFixed(2); // Format value to 2 decimal places
            return `$${value}`; // Show value in dollars
          }
        }
      },
    },
    scales: {
      x: {
        type: 'time',
        time: {
          unit: 'month',
        },
        title: {
          display: true,
          text: 'Date',
        },
      },
      y: {
        title: {
          display: true,
          text: 'Value (USD)',
        },
        ticks: {
          callback: (value) => `$${value.toFixed(2)}`, // Format y-axis labels
        },
      },
    },
  };

  return (
    <div>
      <h2>Total Herd Value Over Time</h2>
      <Line data={herdData} options={options} />
    </div>
  );
};

// Average Value Comparison Chart
const AverageValueComparisonChart = ({ cattleList, startDate, endDate }) => {
  const calculateAverageValues = (cattleList, startDate, endDate) => {
    const valueMap = {};
    const filteredCattleList = cattleList.map(cattle => ({
      ...cattle,
      values: cattle.values.filter(v => new Date(v.date) >= new Date(startDate) && new Date(v.date) <= new Date(endDate)),
    }));
  
    console.log('Filtered Cattle List:', filteredCattleList); // Debugging line
  
    filteredCattleList.forEach(cattle => {
      cattle.values.forEach(v => {
        if (!valueMap[v.date]) {
          valueMap[v.date] = { total: 0, count: 0 };
        }
        valueMap[v.date].total += v.value * cattle.weight / 100; // Convert cents to dollars
        valueMap[v.date].count += 1;
      });
    });
  
    console.log('Value Map:', valueMap); // Debugging line
  
    return Object.keys(valueMap).map(date => ({
      x: date,
      y: valueMap[date].total / valueMap[date].count, // Average value
    }));
  };

  const averageData = {
    labels: [], // Empty because time data will be dynamic
    datasets: [{
      label: 'Average Cattle Value',
      data: calculateAverageValues(cattleList, startDate, endDate),
      borderColor: 'rgba(255, 159, 64, 1)',
      backgroundColor: 'rgba(255, 159, 64, 0.5)',
      fill: false,
    }],
  };

  const options = {
    responsive: true,
    plugins: {
      legend: {
        position: 'top',
        display: false, // Hide legend in the average value chart
      },
      tooltip: {
        mode: 'index',
        intersect: false,
        callbacks: {
          label: function(context) {
            const value = context.raw.y.toFixed(2); // Format value to 2 decimal places
            return `$${value}`; // Show value in dollars
          }
        }
      },
    },
    scales: {
      x: {
        type: 'time',
        time: {
          unit: 'month',
        },
        title: {
          display: true,
          text: 'Date',
        },
      },
      y: {
        title: {
          display: true,
          text: 'Average Value (USD)',
        },
        ticks: {
          callback: (value) => `$${value.toFixed(2)}`, // Format y-axis labels
        },
      },
    },
  };

  return (
    <div>
      <h2>Average Cattle Value Comparison</h2>
      <Line data={averageData} options={options} />
    </div>
  );
};

// Value Distribution Chart
const ValueDistributionChart = ({ cattle }) => {
  if (!cattle || !cattle.values) {
    return <div>No data available for the selected cattle.</div>;
  }

  const distributionData = {
    labels: cattle.values.map(v => new Date(v.date).toLocaleDateString()),
    datasets: [{
      label: `${cattle.type.replace('_', ' ').toUpperCase()} - Weight: ${cattle.weight} kg`,
      data: cattle.values.map(v => v.value * cattle.weight / 100), // Convert cents to dollars
      borderColor: 'rgba(153, 102, 255, 1)',
      backgroundColor: 'rgba(153, 102, 255, 0.5)',
      fill: false,
      pointStyle: 'circle',
    }],
  };

  const options = {
    responsive: true,
    plugins: {
      legend: {
        position: 'top',
        display: false, // Hide legend in the value distribution chart
      },
      tooltip: {
        mode: 'index',
        intersect: false,
        callbacks: {
          label: function(context) {
            const value = context.raw.toFixed(2); // Format value to 2 decimal places
            return `$${value}`; // Show value in dollars
          }
        }
      },
    },
    scales: {
      x: {
        title: {
          display: true,
          text: 'Date',
        },
      },
      y: {
        title: {
          display: true,
          text: 'Value (USD)',
        },
        ticks: {
          callback: (value) => `$${value.toFixed(2)}`, // Format y-axis labels
        },
      },
    },
  };

  return (
    <div>
      <h2>Value Distribution of Selected Cattle</h2>
      <Line data={distributionData} options={options} />
    </div>
  );
};

ValueDistributionChart.propTypes = {
  cattle: PropTypes.shape({
    type: PropTypes.string,
    weight: PropTypes.number,
    values: PropTypes.arrayOf(PropTypes.shape({
      date: PropTypes.string,
      value: PropTypes.number,
    })),
  }),
};

ValueDistributionChart.defaultProps = {
  cattle: {
    type: '',
    weight: 0,
    values: [],
  },
};

// Main component
const CattleValueCharts = ({ cattleList, startDate, endDate, selectedCattle }) => {
  return (
    <div>
      <IndividualCattleValueChart cattleList={cattleList} />
      <TotalHerdValueChart cattleList={cattleList} />
      {/* <AverageValueComparisonChart cattleList={cattleList} startDate={startDate} endDate={endDate} />
      {selectedCattle ? (
        <ValueDistributionChart cattle={selectedCattle} />
      ) : (
        <div>No cattle selected</div>
      )} */}
    </div>
  );
};


export default CattleValueCharts;
