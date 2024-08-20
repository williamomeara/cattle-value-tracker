import React from 'react';
import { Bar } from 'react-chartjs-2';
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend } from 'chart.js';

// Register the necessary components for Chart.js
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
);

const ValueDistributionChart = ({ cattle, bins = 10 }) => {
  const valueDistribution = (cattle, bins) => {
    const data = cattle.values.map(v => v.value * cattle.weight / 100);
    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = (max - min) / bins;
    const distribution = Array(bins).fill(0);

    data.forEach(value => {
      const bin = Math.floor((value - min) / range);
      if (bin < bins) {
        distribution[bin]++;
      }
    });

    return {
      labels: Array.from({ length: bins }, (_, i) => `${(min + i * range).toFixed(2)} - ${(min + (i + 1) * range).toFixed(2)}`),
      datasets: [{
        label: 'Value Distribution',
        data: distribution,
        backgroundColor: 'rgba(75, 192, 192, 0.5)',
      }],
    };
  };

  const distData = valueDistribution(cattle, bins);

  const options = {
    responsive: true,
    plugins: {
      legend: {
        position: 'top',
      },
      tooltip: {
        callbacks: {
          label: function(context) {
            const value = context.raw;
            return `${value}`;
          }
        }
      },
    },
    scales: {
      x: {
        title: {
          display: true,
          text: 'Value Range',
        },
      },
      y: {
        title: {
          display: true,
          text: 'Frequency',
        },
      },
    },
  };

  return (
    <div>
      <h2>Value Distribution for Selected Cattle</h2>
      <Bar data={distData} options={options} />
    </div>
  );
};

export default ValueDistributionChart;
